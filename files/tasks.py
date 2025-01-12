import logging
from celery import shared_task
from .models import FileInfo
from django.db import transaction
from .fproc import save_file_relationships

# 设置日志
logger = logging.getLogger('celery')
logger.setLevel(logging.INFO)


# 保存文件信息，异步处理文件上传
@shared_task
def save_file_data(file_name, file_md5, mime, file_size, file_type, img_wh, file_data, album, subject, level, file_dir, tags, category_id):
    logger.info(f"开始处理文件上传任务 - 文件名: {file_name} (MD5:{file_md5})")

    try:
        logger.info(f"准备创建 FileInfo 对象，用以保存文件信息 - 文件名: {file_name}")
        file_info = FileInfo(
            name=file_name,
            md5=file_md5,
            mime=mime,
            size=file_size,
            type=file_type,
            wh=img_wh,
            album=album,
            subject=subject,
            level=level,
            data=file_data,
            source_addr=file_dir
        )

        # 异步任务内部开启事务
        with transaction.atomic():
            # 保存文件信息
            logger.info(f"开始保存数据信息 - 文件名: {file_name} (MD5:{file_md5})，请稍等......")
            file_info.save()
            logger.info(f"文件信息已成功保存 - 文件名: {file_name} (MD5:{file_md5})！")
            # 保存文件分类/标签
            save_file_relationships(file_info, tags, category_id)
            logger.info(f"文件与C/T关系保存成功 - 文件名: {file_name} (MD5:{file_md5})！")

    except Exception as e:
        logger.error(f"处理文件 {file_name} (MD5:{file_md5}) 时发生错误：{e}", exc_info=True)
        raise  # 重新抛出异常，确保Celery能够正确处理失败情况

