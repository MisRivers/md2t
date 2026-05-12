#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gunicorn 配置文件
"""

import os
import multiprocessing

# 绑定地址
bind = os.environ.get('BIND', '0.0.0.0:5000')

# 工作进程数
workers = multiprocessing.cpu_count() * 2 + 1

# 工作模式
worker_class = 'sync'

# 超时时间
timeout = 30

# 保持连接时间
keepalive = 2

# 错误日志
errorlog = '-'

# 访问日志
accesslog = '-'

# 日志级别
loglevel = 'info'

# 进程名称
proc_name = 'md2t'

# 守护进程模式（生产环境建议开启）
daemon = False

# PID 文件
pidfile = '/tmp/md2t.pid'

# 预加载应用
preload_app = True
