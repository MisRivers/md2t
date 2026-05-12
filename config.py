#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件
"""

import os
from datetime import timedelta
from werkzeug.security import generate_password_hash


class Config:
    """基础配置"""
    # 安全密钥
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("必须设置 SECRET_KEY 环境变量")
    
    # 数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///md2t.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 管理员账号
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH')
    if not ADMIN_PASSWORD_HASH:
        # 如果没有设置密码哈希，使用默认密码 admin123
        ADMIN_PASSWORD_HASH = generate_password_hash('admin123')
    
    # 站点配置
    DOMAIN = os.environ.get('DOMAIN', 'http://127.0.0.1:5000')
    BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')
    
    # 上传限制
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    
    # Session 配置
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # 企业微信限制
    WECHAT_TEXTCARD_TITLE_MAX = 128
    WECHAT_TEXTCARD_DESC_MAX = 512
    WECHAT_TEXT_CONTENT_MAX = 2048
    
    # 数据配置
    DATA_RETENTION_DAYS = int(os.environ.get('DATA_RETENTION_DAYS', 7))
    MAX_LINES = int(os.environ.get('MAX_LINES', 20))
    MAX_TEXT_LENGTH = int(os.environ.get('MAX_TEXT_LENGTH', 4096))


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
