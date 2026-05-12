#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据清理脚本
用于定期清理过期数据
"""

import os
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, ProxyLog


def cleanup_expired_data():
    """清理过期数据"""
    with app.app_context():
        # 查找过期记录
        expired_logs = ProxyLog.query.filter(
            ProxyLog.expires_at < datetime.utcnow()
        ).all()
        
        count = len(expired_logs)
        
        if count == 0:
            print("没有需要清理的过期数据")
            return
        
        # 删除过期记录
        for log in expired_logs:
            db.session.delete(log)
        
        db.session.commit()
        print(f"成功清理 {count} 条过期记录")


def cleanup_old_logs(days=30):
    """清理指定天数前的所有日志"""
    with app.app_context():
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        old_logs = ProxyLog.query.filter(
            ProxyLog.created_at < cutoff_date
        ).all()
        
        count = len(old_logs)
        
        if count == 0:
            print(f"没有超过 {days} 天的旧数据")
            return
        
        for log in old_logs:
            db.session.delete(log)
        
        db.session.commit()
        print(f"成功清理 {count} 条超过 {days} 天的旧记录")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='md2t 数据清理工具')
    parser.add_argument('--expired', action='store_true', 
                        help='清理已过期数据（默认）')
    parser.add_argument('--old', type=int, metavar='DAYS',
                        help='清理指定天数前的所有数据')
    
    args = parser.parse_args()
    
    if args.old:
        cleanup_old_logs(args.old)
    else:
        cleanup_expired_data()
