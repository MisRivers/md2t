# md2t - Markdown to TextCard Proxy

企业微信 Webhook 代理中转站，自动将 Markdown 格式内容转换为 TextCard 或 Text 消息格式。

## 功能特性

- 📝 **自动识别 Markdown**：智能检测 Markdown 语法特征，自动转换
- 🎨 **TextCard 消息**：将 Markdown 转换为企业微信卡片消息格式
- 🔗 **点击查看详情**：转换后的消息附带链接，点击可查看完整 Markdown 渲染页面
- 📊 **后台管理**：完整的日志记录、统计分析、数据管理
- 🔒 **安全可靠**：数据加密存储，7天自动过期，后台权限验证
- ⚡ **高性能**：限流保护，支持高并发

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件
export SECRET_KEY=your-secret-key-here
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD_HASH=admin123
export BASE_URL="http://127.0.0.1:5000"
```

### 3. 启动服务

```bash
# 开发模式
python app.py

# 生产模式（使用 Gunicorn）
gunicorn -c gunicorn.conf.py wsgi:app
```

## 使用说明

### Webhook 地址转换

将原有的企业微信 Webhook 地址进行简单转换：

| 类型 | 地址格式 |
|------|----------|
| 原地址 | `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx` |
| 代理地址 | `https://你的域名或IP:5000/https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx` |

### 发送消息示例

```bash
curl -X POST \
  'https://你的域名或IP:5000/https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx' \
  -H 'Content-Type: application/json' \
  -d '{
    "msgtype": "text",
    "text": {
        "content": "# 系统告警\n\n**服务**: API Gateway\n**状态**: ❌ 异常\n**时间**: 2024-01-15 10:30:00"
    }
}'
```

### 转换逻辑

1. **检测到 Markdown 格式** → 自动转换为 **TextCard** 消息
2. **内容过长**（>500字符）→ 转换为 **Text** 消息附带链接
3. **非 Markdown 格式** → **原文转发**

## 后台管理

访问 `/admin` 进入管理后台：

- **控制台**：查看统计数据、7日趋势图
- **日志列表**：查看所有代理请求记录
- **日志详情**：查看请求内容、响应信息
- **数据清理**：手动清理过期数据

默认账号：
- 用户名：`admin`
- 密码：`admin123`（请在生产环境修改）

## 部署指南

### Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name md2t.misrivers.cn;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Systemd 服务

```ini
# /etc/systemd/system/md2t.service
[Unit]
Description=md2t Markdown to TextCard Proxy
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/md2t
Environment="PATH=/opt/md2t/venv/bin"
Environment="SECRET_KEY=your-secret-key"
Environment="ADMIN_PASSWORD_HASH=your-password-hash"
ExecStart=/opt/md2t/venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl enable md2t
sudo systemctl start md2t
```

## 项目结构

```
md2t/
├── app.py              # 主应用
├── config.py           # 配置文件
├── wsgi.py             # WSGI 入口
├── requirements.txt    # 依赖列表
├── gunicorn.conf.py    # Gunicorn 配置
├── .env.example        # 环境变量示例
├── templates/          # HTML 模板
│   ├── base.html
│   ├── index.html
│   ├── admin_*.html
│   ├── view_markdown.html
│   └── error.html
└── README.md
```

## 安全建议

1. **修改默认密码**：部署后立即修改管理员默认密码
2. **使用 HTTPS**：生产环境务必使用 HTTPS
3. **设置强密钥**：SECRET_KEY 使用随机生成的强密钥
4. **限制访问**：后台管理建议限制 IP 访问
5. **定期备份**：定期备份数据库文件

## 技术栈

- **后端**：Python 3.11 + Flask
- **数据库**：SQLite（可替换为 PostgreSQL/MySQL）
- **前端**：Bootstrap 5 + Chart.js
- **部署**：Gunicorn + Nginx

## License

MIT License
