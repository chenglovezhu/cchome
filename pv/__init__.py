# pv/__init__.py
from __future__ import absolute_import, unicode_literals

import pymysql
pymysql.install_as_MySQLdb()

# 确保在 Django 启动时加载 Celery 配置
from .celery import app as celery_app

__all__ = ('celery_app',)

