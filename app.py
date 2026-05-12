#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown to Text Proxy (md2t)
企业微信Webhook代理中转站
"""

import os
import re
import json
import hashlib
import secrets
import html
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

from flask import Flask, request, jsonify, render_template, abort, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
import markdown
from werkzeug.security import generate_password_hash, check_password_hash

# 配置
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///md2t.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH') or 'scrypt:32768:8:1$aMwbN4Eo7R13BKFJ$8b7e0dd3bfa4ac758a1ab2a5fd20d3c2415089adad6ec7f4d9edf72b12a6c89e1d20979eed01419a04418ce4af380ed4673153234977ecc0601f1c358e9ecdd1'
    DOMAIN = os.environ.get('DOMAIN') or 'http://127.0.0.1:5000'
    BASE_URL = os.environ.get('BASE_URL') or 'http://127.0.0.1:5000'
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    DATA_RETENTION_DAYS = int(os.environ.get('DATA_RETENTION_DAYS') or 7)
    MAX_LINES = int(os.environ.get('MAX_LINES') or 20)
    MAX_TEXT_LENGTH = int(os.environ.get('MAX_TEXT_LENGTH') or 4096)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    # 企业微信限制
    WECHAT_Text_TITLE_MAX = 128
    WECHAT_Text_DESC_MAX = 512
    WECHAT_TEXT_CONTENT_MAX = 2048

app = Flask(__name__)
app.config.from_object(Config)

# 限流器
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# 数据库
db = SQLAlchemy(app)

# ============== Jinja2 过滤器 ==============

@app.template_filter('localtime')
def localtime_filter(utc_dt):
    """将 UTC 时间转换为本地时间（北京时间 UTC+8）"""
    if utc_dt is None:
        return ''
    from datetime import timedelta
    # 北京时间 = UTC + 8小时
    local_dt = utc_dt + timedelta(hours=8)
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')


@app.template_filter('localdate')
def localdate_filter(utc_dt):
    """将 UTC 时间转换为本地日期时间（简短格式）"""
    if utc_dt is None:
        return ''
    from datetime import timedelta
    local_dt = utc_dt + timedelta(hours=8)
    return local_dt.strftime('%m-%d %H:%M')


# ============== 数据库模型 ==============

class ProxyLog(db.Model):
    """代理请求日志"""
    __tablename__ = 'proxy_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    webhook_url = db.Column(db.Text, nullable=False)
    original_content = db.Column(db.Text)
    content_type = db.Column(db.String(20), default='unknown')  # markdown, text, json
    is_markdown = db.Column(db.Boolean, default=False)
    converted_content = db.Column(db.Text)
    response_status = db.Column(db.Integer)
    response_body = db.Column(db.Text)
    client_ip = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    view_count = db.Column(db.Integer, default=0)
    
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self):
        return {
            'id': self.id,
            'request_id': self.request_id,
            'webhook_url': self._mask_webhook_url(),
            'content_type': self.content_type,
            'is_markdown': self.is_markdown,
            'response_status': self.response_status,
            'client_ip': self.client_ip,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_expired': self.is_expired(),
            'view_count': self.view_count
        }
    
    def _mask_webhook_url(self):
        """脱敏处理webhook URL"""
        if not self.webhook_url:
            return ''
        try:
            parsed = urlparse(self.webhook_url)
            if 'key=' in self.webhook_url:
                return re.sub(r'key=[^&]+', 'key=***', self.webhook_url)
            return self.webhook_url[:50] + '...' if len(self.webhook_url) > 50 else self.webhook_url
        except:
            return '***'


class AdminUser(db.Model):
    """管理员用户"""
    __tablename__ = 'admin_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============== 工具函数 ==============

def generate_request_id():
    """生成唯一请求ID"""
    return hashlib.sha256(
        f"{datetime.utcnow().isoformat()}{secrets.token_hex(16)}".encode()
    ).hexdigest()[:16]


def is_markdown_content(content):
    """
    判断内容是否为Markdown格式
    通过检测常见的Markdown语法特征
    """
    if not content or not isinstance(content, str):
        return False
    
    # Markdown特征模式
    md_patterns = [
        r'^#{1,6}\s+',           # 标题
        r'\*\*.*?\*\*',          # 粗体
        r'\*.*?\*',              # 斜体
        r'`[^`]+`',              # 行内代码
        r'```[\s\S]*?```',       # 代码块
        r'\[.*?\]\(.*?\)',       # 链接
        r'!\[.*?\]\(.*?\)',      # 图片
        r'^\s*[-*+]\s+',         # 列表
        r'^\s*\d+\.\s+',         # 有序列表
        r'^\s*>\s+',             # 引用
        r'^\s*---\s*$',          # 分隔线
        r'\|.*?\|',              # 表格
    ]
    
    content_lines = content.split('\n')
    md_feature_count = 0
    
    for line in content_lines:
        for pattern in md_patterns:
            if re.search(pattern, line, re.MULTILINE):
                md_feature_count += 1
                break
    
    # 如果超过2行包含Markdown特征，认为是Markdown
    return md_feature_count >= 2 or (len(content_lines) <= 3 and md_feature_count > 0)


def extract_title_from_markdown(md_content):
    """从Markdown中提取标题"""
    lines = md_content.split('\n')
    
    # 优先找一级标题
    for line in lines:
        match = re.match(r'^#\s+(.+)$', line.strip())
        if match:
            return match.group(1).strip()[:Config.WECHAT_Text_TITLE_MAX]
    
    # 找二级标题
    for line in lines:
        match = re.match(r'^##\s+(.+)$', line.strip())
        if match:
            return match.group(1).strip()[:Config.WECHAT_Text_TITLE_MAX]
    
    # 取第一行非空文本
    for line in lines:
        stripped = line.strip()
        if stripped:
            # 移除Markdown标记
            clean = re.sub(r'[#*`\[\]!]', '', stripped)
            return clean[:Config.WECHAT_Text_TITLE_MAX] if clean else 'Markdown消息'
    
    return 'Markdown消息'


def convert_markdown_to_markdown(md_content, view_url):
    """
    将Markdown转换为企业微信Markdown格式（带查看链接）
    企业微信Webhook支持markdown类型
    """
    # 截断内容（企业微信限制4096字节）
    max_len = 2048  # 留一些余量给链接
    content = md_content
    if len(content) > max_len:
        content = content[:max_len - 50] + '\n\n...（内容已截断）'
    
    # 添加查看链接
    content += f"\n\n[📄 查看完整内容]({view_url})"
    
    return {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }


def convert_markdown_to_text(md_content, view_url):
    """
    将Markdown转换为企业微信Text格式（带链接）
    文本太长时只显示前 MAX_LINES 行
    """
    # 提取纯文本
    lines = md_content.split('\n')
    text_lines = []
    
    for line in lines:
        # 移除Markdown标记
        clean = re.sub(r'\*\*(.+?)\*\*', r'\1', line)  # 粗体
        clean = re.sub(r'\*(.+?)\*', r'\1', clean)      # 斜体
        clean = re.sub(r'`(.+?)`', r'\1', clean)        # 代码
        clean = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', clean)  # 链接
        clean = re.sub(r'!\[.*?\]\(.+?\)', '[图片]', clean)  # 图片
        clean = re.sub(r'^#+\s*', '', clean)             # 标题标记
        clean = re.sub(r'^\s*[-*+]\s*', '• ', clean)     # 列表
        clean = re.sub(r'^\s*\d+\.\s*', '', clean)       # 有序列表
        clean = re.sub(r'^>\s*', '', clean)              # 引用
        
        if clean.strip():
            text_lines.append(clean)
    
    # 超过 MAX_LINES 时截断
    is_truncated = False
    if len(text_lines) > Config.MAX_LINES:
        text_lines = text_lines[:Config.MAX_LINES]
        is_truncated = True
    
    content = '\n'.join(text_lines)
    
    # 字符长度限制
    max_len = Config.MAX_TEXT_LENGTH - len(view_url) - 60
    if len(content) > max_len:
        content = content[:max_len - 3] + '...'
        is_truncated = True
    
    # 拼接查看链接
    if is_truncated:
        content += f"\n\n...（内容已截断）\n📄 查看完整内容: {view_url}"
    else:
        content += f"\n\n📄 查看完整内容: {view_url}"
    
    return {
        "msgtype": "text",
        "text": {
            "content": content,
            "mentioned_list": [],
            "mentioned_mobile_list": []
        }
    }


def parse_webhook_url_from_path(path):
    """
    从请求路径中解析企业微信Webhook URL
    格式: /https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
    """
    # 去掉可能的开头 /
    if path.startswith('/'):
        path = path[1:]
    
    # 检查是否以 https:// 开头
    if path.startswith('https://'):
        # 验证是否是有效的企业微信Webhook URL
        if re.match(r'^https://qyapi\.weixin\.qq\.com/cgi-bin/webhook/send', path):
            return path
    
    return None


def require_admin(f):
    """管理员权限装饰器"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            if request.is_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    
    return decorated_function


# ============== 路由 ==============

@app.route('/')
def index():
    """首页"""
    return render_template('index.html', domain=app.config['DOMAIN'])


def get_admin_password_hash():
    """获取管理员密码哈希，优先从数据库读取（支持修改），否则用配置默认值"""
    user = AdminUser.query.filter_by(username=app.config['ADMIN_USERNAME']).first()
    if user and user.password_hash:
        return user.password_hash
    return app.config['ADMIN_PASSWORD_HASH']


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """管理员登录"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # 验证凭据（优先从数据库读取密码哈希）
        if (username == app.config['ADMIN_USERNAME'] and 
            check_password_hash(get_admin_password_hash(), password)):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session.permanent = True
            
            # 记录登录时间
            user = AdminUser.query.filter_by(username=username).first()
            if user:
                user.last_login = datetime.utcnow()
                db.session.commit()
            else:
                user = AdminUser(
                    username=username,
                    password_hash=app.config['ADMIN_PASSWORD_HASH']
                )
                db.session.add(user)
                db.session.commit()
            
            return redirect(url_for('admin_dashboard'))
        
        flash('用户名或密码错误', 'error')
    
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    """管理员登出"""
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin/password', methods=['GET', 'POST'])
@require_admin
def admin_change_password():
    """修改管理员密码"""
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # 验证旧密码
        if not check_password_hash(get_admin_password_hash(), old_password):
            flash('当前密码错误', 'error')
            return redirect(url_for('admin_change_password'))
        
        # 验证新密码
        if len(new_password) < 6:
            flash('新密码长度不能少于6位', 'error')
            return redirect(url_for('admin_change_password'))
        
        if new_password != confirm_password:
            flash('两次输入的新密码不一致', 'error')
            return redirect(url_for('admin_change_password'))
        
        if old_password == new_password:
            flash('新密码不能与当前密码相同', 'error')
            return redirect(url_for('admin_change_password'))
        
        # 更新密码到数据库
        user = AdminUser.query.filter_by(username=app.config['ADMIN_USERNAME']).first()
        new_hash = generate_password_hash(new_password)
        
        if user:
            user.password_hash = new_hash
        else:
            user = AdminUser(
                username=app.config['ADMIN_USERNAME'],
                password_hash=new_hash
            )
            db.session.add(user)
        
        db.session.commit()
        flash('密码修改成功，下次登录时生效', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_change_password.html')


@app.route('/admin')
@app.route('/admin/dashboard')
@require_admin
def admin_dashboard():
    """管理后台首页"""
    # 统计数据
    total_count = ProxyLog.query.count()
    today_count = ProxyLog.query.filter(
        db.func.date(ProxyLog.created_at) == db.func.date('now')
    ).count()
    markdown_count = ProxyLog.query.filter_by(is_markdown=True).count()
    expired_count = ProxyLog.query.filter(ProxyLog.expires_at < datetime.utcnow()).count()
    
    # 最近10条记录
    recent_logs = ProxyLog.query.order_by(ProxyLog.created_at.desc()).limit(10).all()
    
    return render_template('admin_dashboard.html',
                         total_count=total_count,
                         today_count=today_count,
                         markdown_count=markdown_count,
                         expired_count=expired_count,
                         recent_logs=recent_logs)


@app.route('/admin/logs')
@require_admin
def admin_logs():
    """日志列表"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = ProxyLog.query.order_by(ProxyLog.created_at.desc())
    
    # 筛选
    content_type = request.args.get('content_type')
    if content_type:
        query = query.filter_by(content_type=content_type)
    
    is_markdown = request.args.get('is_markdown')
    if is_markdown is not None:
        query = query.filter_by(is_markdown=(is_markdown == '1'))
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    logs = pagination.items
    
    return render_template('admin_logs.html', logs=logs, pagination=pagination)


@app.route('/admin/logs/<request_id>')
@require_admin
def admin_log_detail(request_id):
    """日志详情"""
    log = ProxyLog.query.filter_by(request_id=request_id).first_or_404()
    return render_template('admin_log_detail.html', log=log)


@app.route('/admin/logs/<request_id>/delete', methods=['POST'])
@require_admin
def admin_log_delete(request_id):
    """删除日志"""
    log = ProxyLog.query.filter_by(request_id=request_id).first_or_404()
    db.session.delete(log)
    db.session.commit()
    flash('记录已删除', 'success')
    return redirect(url_for('admin_logs'))


@app.route('/admin/cleanup', methods=['POST'])
@require_admin
def admin_cleanup():
    """清理过期数据"""
    expired_logs = ProxyLog.query.filter(ProxyLog.expires_at < datetime.utcnow()).all()
    count = len(expired_logs)
    
    for log in expired_logs:
        db.session.delete(log)
    
    db.session.commit()
    flash(f'已清理 {count} 条过期记录', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/api/stats')
@require_admin
def admin_api_stats():
    """API统计数据"""
    # 按天的统计
    daily_stats = db.session.query(
        db.func.date(ProxyLog.created_at).label('date'),
        db.func.count(ProxyLog.id).label('count'),
        db.func.sum(db.case([(ProxyLog.is_markdown == True, 1)], else_=0)).label('md_count')
    ).group_by(db.func.date(ProxyLog.created_at)).order_by(db.desc('date')).limit(30).all()
    
    return jsonify({
        'daily': [
            {
                'date': str(stat.date),
                'total': stat.count,
                'markdown': stat.md_count
            }
            for stat in daily_stats
        ]
    })


@app.route('/view/<request_id>')
def view_markdown(request_id):
    """
    Markdown展示页面
    有效期7天
    """
    try:
        log = ProxyLog.query.filter_by(request_id=request_id).first()
    except Exception:
        abort(500, description='数据库查询失败')
    
    if not log:
        abort(404, description='内容不存在')
    
    # 检查是否过期
    if log.is_expired():
        abort(410, description='该内容已过期（有效期7天）')
    
    # 增加查看次数
    try:
        log.view_count += 1
        db.session.commit()
    except Exception:
        pass
    
    # 转换Markdown为HTML
    try:
        if log.original_content:
            html_content = markdown.markdown(
                log.original_content,
                extensions=['tables', 'fenced_code', 'nl2br']
            )
        else:
            html_content = '<p class="text-muted">无内容</p>'
    except Exception:
        html_content = f'<pre>{html.escape(log.original_content or "")}</pre>'
    
    return render_template('view_markdown.html',
                         log=log,
                         html_content=html_content,
                         title=extract_title_from_markdown(log.original_content or ''))


@app.route('/<path:webhook_path>', methods=['POST', 'GET'])
@limiter.limit("30 per minute")
def proxy_webhook(webhook_path):
    """
    代理企业微信Webhook请求
    支持格式: /https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
    """
    # 构建Webhook URL
    # webhook_path 是 Flask <path:> 捕获的路径部分，如 https://qyapi.weixin.qq.com/cgi-bin/webhook/send
    # request.query_string 包含原始请求的查询参数（如 key=xxx），需要拼接到 webhook URL
    webhook_url = webhook_path
    if request.query_string:
        query_str = request.query_string.decode('utf-8')
        if '?' in webhook_url:
            webhook_url += '&' + query_str
        else:
            webhook_url += '?' + query_str
    
    # 验证是否是有效的企业微信Webhook URL
    if not re.match(r'^https://qyapi\.weixin\.qq\.com/cgi-bin/webhook/send', webhook_url):
        return jsonify({'errcode': -1, 'errmsg': 'Invalid webhook URL format'}), 400
    
    # 生成请求ID
    request_id = generate_request_id()
    
    # 创建日志记录
    log = ProxyLog(
        request_id=request_id,
        webhook_url=webhook_url,
        client_ip=request.headers.get('X-Forwarded-For', request.remote_addr),
        user_agent=request.headers.get('User-Agent', ''),
        expires_at=datetime.utcnow() + timedelta(days=app.config['DATA_RETENTION_DAYS'])
    )
    
    try:
        # 获取请求内容
        content_type = request.headers.get('Content-Type', '')
        log.content_type = 'unknown'
        
        if request.is_json:
            data = request.get_json()
            log.content_type = 'json'
            
            # 获取原始消息类型
            original_msgtype = data.get('msgtype', '')
            
            # 提取原始内容
            original_content = None
            if 'text' in data and 'content' in data['text']:
                original_content = data['text']['content']
                log.content_type = 'text'
            elif 'markdown' in data and 'content' in data['markdown']:
                original_content = data['markdown']['content']
                log.content_type = 'markdown'
            elif 'markdown_v2' in data and 'content' in data['markdown_v2']:
                original_content = data['markdown_v2']['content']
                log.content_type = 'markdown_v2'
            
            log.original_content = original_content
            
            # 判断是否需要转换
            # msgtype 是 markdown 或 markdown_v2 → 全部转为 text
            # msgtype 不是 markdown 但内容是 Markdown → 也转为 text（原文转发也行，但统一处理）
            is_md_msgtype = original_msgtype in ('markdown', 'markdown_v2')
            is_md_content = original_content and is_markdown_content(original_content)
            
            if (is_md_msgtype or is_md_content) and original_content:
                # 统一转为 text 格式
                log.is_markdown = is_md_content
                view_url = f"{app.config['BASE_URL']}/view/{request_id}"
                converted = convert_markdown_to_text(original_content, view_url)
                log.converted_content = json.dumps(converted, ensure_ascii=False)
                data = converted
        else:
            # 非JSON请求，原文转发
            data = request.get_data()
            log.content_type = 'raw'
        
        # 保存日志
        db.session.add(log)
        db.session.commit()
        
        # 转发到企业微信
        headers = {
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        if isinstance(data, dict):
            response = requests.post(webhook_url, json=data, headers=headers, timeout=30)
        else:
            response = requests.post(webhook_url, data=data, headers=headers, timeout=30)
        
        # 更新日志
        log.response_status = response.status_code
        log.response_body = response.text[:2000]  # 限制长度
        db.session.commit()
        
        # 返回企业微信的响应
        return response.text, response.status_code, {'Content-Type': 'application/json'}
        
    except requests.exceptions.RequestException as e:
        log.response_status = 500
        log.response_body = str(e)[:2000]
        db.session.commit()
        return jsonify({'errcode': -1, 'errmsg': f'Proxy error: {str(e)}'}), 500
    
    except Exception as e:
        log.response_status = 500
        log.response_body = str(e)[:2000]
        db.session.commit()
        return jsonify({'errcode': -1, 'errmsg': f'Internal error: {str(e)}'}), 500


# ============== 错误处理 ==============

@app.errorhandler(404)
def not_found(error):
    if request.is_json:
        return jsonify({'errcode': 404, 'errmsg': 'Not found'}), 404
    return render_template('error.html', code=404, message='页面未找到'), 404


@app.errorhandler(410)
def gone(error):
    if request.is_json:
        return jsonify({'errcode': 410, 'errmsg': str(error.description)}), 410
    return render_template('error.html', code=410, message=str(error.description)), 410


@app.errorhandler(429)
def rate_limit(error):
    return jsonify({'errcode': 429, 'errmsg': 'Rate limit exceeded'}), 429


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    if request.is_json:
        return jsonify({'errcode': 500, 'errmsg': 'Internal server error'}), 500
    return render_template('error.html', code=500, message='服务器内部错误'), 500


# ============== 初始化 ==============

def init_db():
    """初始化数据库"""
    with app.app_context():
        db.create_all()
        print("Database initialized.")


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
