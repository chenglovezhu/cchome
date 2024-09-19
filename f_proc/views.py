import os
import uuid
import json
import threading
import logging
import shutil
from datetime import datetime
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import FileInfoForm, FileAppertainForm
from .models import FileInfo, FileRelationship, FileAppertain
from .fproc import get_f_ext, get_md5, reset_auto_increment, generate_encryption_key, convert_to_encrypted_hls

# 设置日志
logger = logging.getLogger("f_proc")
# 用于存储任务状态的字典
v2hls_task_status = {}
# 用于保护 task_status 字典的锁
v2hls_task_status_lock = threading.Lock()

# 定义404页面
def custom_404_view(request, exception):
    return render(request, 'f_proc/404.html', status=404)

# 上传文件页面
def upload(request):
    try:
        categories = FileAppertain.objects.filter(flag="C")
    except Exception as e:
        logger.error(f"获取分类时出错: {str(e)}")
        categories = []  # 错误情况下使用空列表
    return render(request, 'f_proc/upload.html', {'categories': categories})

# 文件清单页面
def file_list(request):
    try:
        file_info_list = FileInfo.objects.all().order_by('-created_time')
    except Exception as e:
        logger.error(f"获取文件列表时出错: {str(e)}")
        file_info_list = FileInfo.objects.none()  # 遇到错误时返回空查询集
    
    paginator = Paginator(file_info_list, 15)  # 每页显示15个文件
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'f_proc/list.html', {'page_obj': page_obj})

# 建立文件与分类/标签关系
def create_file_relationship(file_info, appertain_id=None, appertain_name=None, flag='T', parent=0):
    if appertain_id:
        file_appertain = FileAppertain.objects.get(id=appertain_id)
    elif appertain_name:
        file_appertain, created = FileAppertain.objects.get_or_create(name=appertain_name, flag=flag, parent=parent)
    else:
        return  # 如果没有传入有效的 ID 或名称，则不进行操作

    # 创建 FileRelationship
    FileRelationship.objects.create(file_info=file_info, file_appertain=file_appertain)

# 上传文件，并将数据写入数据库
def handle_uploaded_file(file, file_info):
    # 定义文件分块的大小为1M
    chunk_size = 1024 * 1024  # 1MB
    # 定义文件分块后，每个块数据的位置被保存在该数组中
    file_info.data = []
    # 定义文件块的保存路径
    baseDir = os.path.join('media', timezone.now().strftime('%Y-%m-%d'), file_info.md5)
    
    # 开始处理上传文件：将文件进行分块存储
    try:
        # 创建文件块保存目录
        os.makedirs(baseDir, exist_ok=True)
        # 写入文件块数据
        with file.open('rb') as f:
            while True:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break
                chunk_uuid = str(uuid.uuid4())
                chunk_path = os.path.join(baseDir, chunk_uuid)
                with open(chunk_path, 'wb') as chunk_file:
                    chunk_file.write(chunk_data)
                file_info.data.append(chunk_path)
        
        file_info.data = json.dumps(file_info.data)
        file_info.source_addr = baseDir
        # 重置数据库，保证数据ID顺序自增长
        reset_auto_increment()
        # 将数据保存入数据库
        file_info.save()
        
    except Exception as e:
        logger.error(f"保存文件 {file.name} 时出错: {str(e)}")
        
        # 清理已创建的文件和目录
        for path in json.loads(file_info.data):
            if os.path.exists(path):
                os.remove(path)
        if os.path.exists(baseDir):
            shutil.rmtree(baseDir)
        raise

# 处理上传文件
def save_file_data(request):
    # 如果上传文件，则保存文件
    if request.method == 'POST':
        files = request.FILES.getlist('file_field')
        tags = request.POST.get('manyTags', '').split('/')
        album = request.POST.get('album')
        subject = request.POST.get('subject')
        category_id = request.POST.get('categorySelect')
        level = request.POST.get('levelSelect')

        # 定义上传文件的结果
        upload_result = {"successful":[], 
                         "exist":[], 
                         "failed":[]
                         }
        
        for file in files:
            file_md5 = get_md5(file)
            exist_file = FileInfo.objects.filter(md5=file_md5).first()
            if exist_file:
                upload_result['exist'].append({'name': file.name, 'md5': file_md5})
                continue

            file_info = FileInfo(
                name=file.name,
                mime=file.content_type,
                size=file.size,
                type=get_f_ext(file)['file_extension'],
                album=album,
                subject=subject,
                level=level,
                md5=file_md5,
            )
            
            try:
                # 开始处理上传文件
                handle_uploaded_file(file, file_info)

                for tag in tags:
                    tag = tag.strip()
                    if tag:
                        create_file_relationship(file_info, appertain_name=tag)

                if category_id:
                    create_file_relationship(file_info, appertain_id=category_id)

                upload_result['successful'].append({'name': file.name, 'md5': file_md5})
            except Exception as e:
                upload_result['failed'].append({'name': file.name, 'md5': file_md5})
                logger.error(f"上传文件 {file.name} 时出错: {str(e)}")
                if file_info.id:
                    file_info.delete()
        
        return JsonResponse(upload_result)
    # 如果为访问上传页面，则将分类数据传给页面
    categories = FileAppertain.objects.filter(flag="C")
    return render(request, 'f_proc/upload.html', {'categories': categories})

# 管理分类标签页面
def manage_appertain(request, pk=None):
    appertain = get_object_or_404(FileAppertain, pk=pk) if pk else None
    response_data = {}
    
    if request.method == "POST":
        form = FileAppertainForm(request.POST, instance=appertain)
        name = form.data.get('name')
        flag = form.data.get('flag')
        
        if "add" in request.POST:
            if FileAppertain.objects.filter(name=name, flag=flag).exists():
                response_data['status'] = 'error'
                response_data['message'] = '分类名或标签名已存在！'
            elif form.is_valid():
                form.save()
                response_data['status'] = 'success'
                response_data['message'] = '保存成功！'
            else:
                response_data['status'] = 'error'
                response_data['message'] = '保存失败！'
                
        elif "update" in request.POST:
            if FileAppertain.objects.filter(name=name).exclude(pk=pk).exists():
                response_data['status'] = 'error'
                response_data['message'] = '分类名或标签名已存在！'
            elif form.is_valid():
                form.save()
                response_data['status'] = 'success'
                response_data['message'] = '更新成功！'
            else:
                response_data['status'] = 'error'
                response_data['message'] = '更新失败！'
                
        elif "delete" in request.POST and appertain:
            try:
                appertain.delete()
                response_data['status'] = 'success'
                response_data['message'] = '删除成功！'
            except Exception as e:
                response_data['status'] = 'error'
                response_data['message'] = f'删除失败：{str(e)}'
        
        return JsonResponse(response_data)

    else:
        form = FileAppertainForm(instance=appertain)

    appertains = FileAppertain.objects.filter(flag="C")
    return render(request, 'f_proc/ct.html', {
        'form': form,
        'appertains': appertains,
        'current_appertain': appertain
    })

# 获取文件数据，用以展示与下载
def get_file_data(request, md5):
    try:
        file_obj = FileInfo.objects.get(md5=md5)
        file_obj.data = json.loads(file_obj.data)
        return JsonResponse({'fileName':file_obj.name, 'fileDatas': file_obj.data, 'fileType':file_obj.type, 'fileSize':file_obj.size, 'hlsAddr':file_obj.hls_addr})
    except FileInfo.DoesNotExist:
        return JsonResponse({'error': '文件未找到'}, status=404)
    except Exception as e:
        logger.error(f"获取文件数据时出错: {str(e)}")
        return JsonResponse({'error': '服务器错误'}, status=500)

# 查询文件
def file_search(request):
    try:
        data = request.GET.get('searchFiles', '')
        
        files = FileInfo.objects.all().order_by('-created_time')
        
        if data:
            files = files.filter(Q(name__icontains=data) | Q(md5__icontains=data) | Q(album__icontains=data) | Q(subject=data))

        paginator = Paginator(files, 15)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        tags = FileAppertain.objects.all()
        return render(request, 'f_proc/filter.html', {'page_obj': page_obj, 'tags': tags})
    except Exception as e:
        logger.error(f"文件搜索失败: {str(e)}")
        return render(request, 'f_proc/filter.html', {'page_obj': [], 'tags': []})

# 更新视频转换状态
def update_v2hls_task_status(md5, status, result=''):
    with v2hls_task_status_lock:
        v2hls_task_status[md5] = {'status': status, 'result': result}

def v2hls_task_status_view(request, md5):
    with v2hls_task_status_lock:
        status = v2hls_task_status.get(md5, {'status': '未开始', 'result': ''})
    return JsonResponse(status)

# 将传频文件转为HLS流
def vFile_to_HLS_task(md5):
    try:
        # 查询视频文件是否存在
        exist_file = FileInfo.objects.filter(md5=md5).first()
        if not exist_file:
            logger.error(f"未找到MD5为 {md5} 的视频文件。")
            return
        
        # 提取日期部分
        date_str = exist_file.created_time.date()
        if os.path.exists(f"media/HLS/{date_str}/{md5}"):
            # 更新任务状态为处理中
            update_v2hls_task_status(md5, '处理中', 'HLS视频流已存在，请检查！')
            logger.error(f"{md5}视频文件的视频流已存在")
            return
        
        # 更新任务状态为处理中
        update_v2hls_task_status(md5, '处理中', 'HLS视频流正在生成，请稍等......')

        # 定义视频文件转换路径
        keyDir = os.path.join('media', 'VKey', timezone.now().strftime('%Y-%m-%d'), exist_file.md5)
        hlsDir = os.path.join('media', 'HLS', timezone.now().strftime('%Y-%m-%d'), exist_file.md5)
        vf_path = os.path.join(hlsDir, f"{exist_file.md5}.{exist_file.type}")

        # 创建视频文件目录
        os.makedirs(keyDir, exist_ok=True)
        os.makedirs(hlsDir, exist_ok=True)

        # 合并视频文件块数据 
        with open(vf_path, 'wb') as f:
            # 读取视频文件块数据
            data_list = json.loads(exist_file.data)
            for data in data_list:
                with open(data, 'rb') as cf:
                    f.write(cf.read())

        # 生成视频流密钥
        keyInfo = generate_encryption_key(keyDir)
        # 将视频转换为HLS流
        m3u8 = convert_to_encrypted_hls(vf_path, hlsDir, keyInfo)

        # 将HLS视频流地址保存入数据库
        exist_file.hls_addr = m3u8
        exist_file.save()

        # 移除合成的视频文件，减小磁盘消耗
        if os.path.exists(vf_path):
            os.remove(vf_path)
            
        # 更新任务状态为完成
        update_v2hls_task_status(md5, '完成', '视频文件成功转换为HLS流。')
    
    except Exception as e:
        update_v2hls_task_status(md5, '失败', str(e))
        logger.error(f"处理视频文件 {md5} 时出现未知错误: {e}")

# 将上传视频文件转为HLS流
def vFile_to_HLS(request, md5):
    # 验证md5是否为空或格式不正确
    if not md5 or not isinstance(md5, str) or len(md5) != 32:
        return JsonResponse({"error": "无效的MD5值"}, status=400)

    try:
        # 启动异步任务线程
        thread = threading.Thread(target=vFile_to_HLS_task, args=(md5,))
        thread.start()
    except Exception as e:
        logger.error(f"启动视频转换线程时出错: {e}")
        return JsonResponse({"error": "视频转换任务启动失败"}, status=500)

    # 立即返回响应，不用等待线程执行完毕
    return JsonResponse({"result": "视频流转换任务已启动，请稍等......"})

# 定义转换视频流页面
def v2hls(request):
    return render(request, 'f_proc/v2hls.html')

def check_and_delete_file_chunks(request, md5):
    try:
        # 查询视频文件是否存在
        check_delete_file = FileInfo.objects.filter(md5=md5).first()
        
        if check_delete_file:
            # 确定文件块目录
            base_path = os.path.join('media', check_delete_file.created_time.date().strftime('%Y-%m-%d'), md5)
            
            if os.path.exists(base_path):
                # 获取目录下所有文件
                file_list = os.listdir(base_path)
                
                # 遍历并判断所有的文件
                for file_chunk in file_list:
                    file_chunk_path = os.path.join(base_path, file_chunk)
                    
                    # 如果文件块不在数据中，则删除
                    if file_chunk not in check_delete_file.data:
                        try:
                            os.remove(file_chunk_path)
                        except OSError as e:
                            # 处理删除文件时可能出现的错误
                            logger.error(f"Error deleting file {file_chunk_path}: {e}")
            else:
                return JsonResponse({"校验文件": md5, "status": "文件夹不存在"}, status=404)
        else:
            return JsonResponse({"校验文件": md5, "status": "文件信息不存在"}, status=404)

    except Exception as e:
        # 捕获其他潜在的异常
        return JsonResponse({"校验文件": md5, "status": "校验失败", "error": str(e)}, status=500)

    return JsonResponse({"校验文件": md5, "status": "校验完成！"})

# 将文件状态改为不可用
def set_file_status_disable(request, md5):
    try:
        # 查询文件是否存在
        file_obj = get_object_or_404(FileInfo, md5=md5)
        
        # 将文件状态设为不可用
        file_obj.status = "disable"
        # 保存数据
        file_obj.save()

        # 返回操作结果
        response_data = {
            "status": "successful",
            "fileName": file_obj.name,
            "md5": md5
        }
        return JsonResponse(response_data)

    except Exception as e:
        # 捕获并记录异常
        logger.error(f"文件状态更改错误，MD5 为 {md5}：{e}")
        response_data = {
            "status": "failed",
            "md5": md5,
            "error": str(e)
        }
        return JsonResponse(response_data, status=500)
        
# 将文件状态改为可用
def set_file_status_enable(request, md5):
    try:
        file_obj = get_object_or_404(FileInfo, md5=md5)
        status = file_obj.status

        if status == "disable":
            file_obj.status = "enable"
            file_obj.save()

            response_data = {
                "status": "successful",
                "fileName": file_obj.name,
                "md5": md5,
                "bak": ""
            }
            return JsonResponse(response_data)

        elif status == "delete":
            response_data = {
                "status": "failed",
                "fileName": file_obj.name,
                "md5": md5,
                "bak": f"{file_obj.name} 已被删除！"
            }
            return JsonResponse(response_data, status=404)

        else:
            response_data = {
                "status": "failed",
                "fileName": file_obj.name,
                "md5": md5,
                "bak": f"{file_obj.name} 状态已为 enable"
            }
            return JsonResponse(response_data, status=400)

    except FileInfo.DoesNotExist:
        response_data = {
            "status": "failed",
            "md5": md5,
            "error": "文件不存在"
        }
        return JsonResponse(response_data, status=404)

    except Exception as e:
        logger.error(f"文件状态更改错误，MD5 为 {md5}：{e}")
        response_data = {
            "status": "failed",
            "md5": md5,
            "error": "服务器内部错误"
        }
        return JsonResponse(response_data, status=500)

# 定义删除文件原数据页面
def delete(request):
    return render(request, 'f_proc/delete.html')

# 删除文件原数据
def delete_file(request, md5):
    try:
        # Retrieve the file object or return a 404 if not found
        file_obj = get_object_or_404(FileInfo, md5=md5)
        
        # Determine the file directory based on source_addr or default path
        if file_obj.source_addr:
            file_dir = file_obj.source_addr
        else:
            file_dir = os.path.join('media', file_obj.created_time.strftime('%Y-%m-%d'), file_obj.md5)
        
        # Ensure the directory exists before attempting to remove it
        if os.path.exists(file_dir):
            shutil.rmtree(file_dir)
            try:
                file_obj.status = "delete"
                file_obj.save()
            except Exception as e:
                logger.error(f"文件删除中，数据更新为：'delete' 出现错误：{e}") 
            logger.info(f"Successfully deleted directory: {file_dir}")
            return JsonResponse({"status":"Successful", "content":f"文件源数据已成功删除！"})
        else:
            logger.warning(f"Directory not found: {file_dir}")
            return JsonResponse({"status":"Failed", "content":f"文件源数据已不存在，请检查......"})

    except Exception as e:
        # Log the exception and return an error response
        logger.error(f"Error deleting file: {e}")
    return JsonResponse({"status":"Failed", "content":f"删除文件出错，请联系客服......"})

@require_POST
def update_file_info(request, md5):
    file_obj = get_object_or_404(FileInfo, md5=md5)
    form = FileInfoForm(request.POST, instance=file_obj)
    if form.is_valid():
        form.save()
        response_data = {
            "status": "successful",
            "content": "文件信息更新成功！"
        }
        return JsonResponse(response_data)
    else:
        return JsonResponse({
            "status": "error",
            "content": "更新失败！",
            "errors": form.errors
        }, status=400)
        
# 随机处理页
def random_all(request):
    try:
        file_objs = FileInfo.objects.filter(status="enable").order_by('-created_time')
        # 提取所需字段，比如文件数据块地址
        file_objs_list = [{"id": file_obj.id, "data": file_obj.data, "mime":file_obj.mime, "name":file_obj.name, "md5":file_obj.md5, "album":file_obj.album, "subject":file_obj.subject, "hlsAddr":file_obj.hls_addr, "fileSize":float(file_obj.size)} for file_obj in file_objs]
        file_objs_json = json.dumps(file_objs_list)  # 将列表转换为JSON格式
    except Exception as e:
        logger.error(f"获取文件列表时出错: {str(e)}")
        file_objs_json = json.dumps([])  # 返回空JSON数据

    return render(request, 'f_proc/random.html', {'file_objs': file_objs_json})

# 根据请求随机处理
def random_filter(request):
    try:
        # 从请求中获取查询参数
        level = request.GET.get('level')
        album = request.GET.get('album')
        subject = request.GET.get('subject')

        # 使用这些参数进行过滤
        filters = {"status": "enable"}
        if level:
            filters["level"] = level
        if album:
            filters["album"] = album
        if subject:
            filters["subject"] = subject

        # 查询数据库
        file_objs = FileInfo.objects.filter(**filters).order_by('-created_time')

        # 生成响应数据
        file_objs_list = [{"id": file_obj.id, "data": file_obj.data, "mime":file_obj.mime, "name":file_obj.name, "md5":file_obj.md5, "album":file_obj.album, "subject":file_obj.subject, "hlsAddr":file_obj.hls_addr, "fileSize":float(file_obj.size)} for file_obj in file_objs]
        file_objs_json = json.dumps(file_objs_list)  # 将列表转换为JSON格式
        
    except Exception as e:
        logger.error(f"获取文件列表时出错: {str(e)}")
        file_objs_json = json.dumps([])  # 返回空JSON数据
    
    return render(request, 'f_proc/random.html', {'file_objs': file_objs_json})
