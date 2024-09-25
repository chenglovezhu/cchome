import uuid
from decimal import Decimal
from django.db import models


class FileInfo(models.Model):
    name = models.TextField()
    code = models.UUIDField(default=uuid.uuid4, editable=False)
    md5 = models.CharField(max_length=32)
    size = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))
    type = models.CharField(max_length=16, default="unknown")
    mime = models.CharField(max_length=128, default="unknown")
    wh = models.JSONField(null=True, blank=True)
    level = models.CharField(max_length=16, default="General")
    data = models.JSONField(null=True, blank=True)
    created_time = models.DateTimeField(auto_now_add=True)
    delete_time = models.DateTimeField(null=True, blank=True)
    author = models.CharField(max_length=64, null=True, blank=True)
    album = models.TextField(null=True, blank=True)
    subject = models.TextField(null=True, blank=True)
    hls_addr = models.CharField(max_length=128,null=True, blank=True)
    thumbnail_addr = models.CharField(max_length=128, null=True, blank=True)
    source_addr = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=16, default="enable")
    remark = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'file_info'

class FileAppertain(models.Model):
    FLAG_CHOICES = [
        ("C", "Catalogue"),
        ("T", "Tag"),
    ]
    name = models.CharField(max_length=128, unique=True)
    flag = models.CharField(max_length=1, choices=FLAG_CHOICES)
    parent = models.IntegerField(default=0)  # 默认 parent 为 0

    class Meta:
        db_table = 'file_appertain'

class FileRelationship(models.Model):
    file_info = models.ForeignKey(FileInfo, on_delete=models.CASCADE, related_name='relationships')
    file_appertain = models.ForeignKey(FileAppertain, on_delete=models.CASCADE, related_name='relationships')

    class Meta:
        db_table = 'file_relationship'