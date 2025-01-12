from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
import logging
from django.conf import settings
from celery.signals import setup_logging

# 设置环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pv.settings')

# 创建 Celery 实例
app = Celery('pv')

# 使用 Django 配置的 settings.py 中的 Celery 配置
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现项目中所有的 Celery 任务（在每个 Django app 下的 tasks.py 文件中）
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# 配置broker版本
app.conf.update(
    broker_connection_retry_on_startup=True,
)

# 日志配置
@setup_logging.connect
def configure_logging(sender=None, **kwargs):
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s %(asctime)s %(module)s %(message)s',
        handlers=[
            logging.FileHandler('logs/celery.log'),
            logging.StreamHandler()
        ]
    )




