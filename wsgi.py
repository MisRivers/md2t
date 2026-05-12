#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSGI 入口文件
用于 Gunicorn 部署
"""

import os
from app import app, init_db

# 获取环境配置
env = os.environ.get('FLASK_ENV', 'production')

# 初始化数据库
init_db()

if __name__ == "__main__":
    app.run()
