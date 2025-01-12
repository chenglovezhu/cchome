import os
import json
import logging
import shutil
import aiofiles
from tqdm import tqdm
from django.utils import timezone
from django.db.models import Q, Count
from django.db import transaction
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.core.cache import cache
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import FileInfo, FileAppertain, FileRelationship
from .tasks import save_file_data
from .fproc import get_md5, get_image_wh, get_f_ext,handle_uploaded_file,generate_encryption_key,convert_to_encrypted_hls
from .forms import FileInfoForm, FileAppertainForm
from channels.layers import get_channel_layer
from django.http import HttpResponseBadRequest
from asgiref.sync import sync_to_async

# Create your views here.
# 设置日志
logger = logging.getLogger("files")


# 应用启动后加载数据到redis,数据以字典形式存在
def load_data_to_cache(request):
    try:
        # 获取所有文件对象
        file_objs = FileInfo.objects.all()
        
        # 遍历文件对象并将其缓存到redis中
        for file_obj in tqdm(file_objs, desc="正在加载数据", unit="Data"):
            # 准备缓存数据
            file_obj_data = {
                "name": file_obj.name,
                "code": file_obj.code, 
                "size": str(file_obj.size), 
                "type": file_obj.type, 
                "mime": file_obj.mime, 
                "wh": file_obj.wh, 
                "level": file_obj.level, 
                "data": file_obj.data, 
                "created_time": str(file_obj.created_time), 
                "delete_time": str(file_obj.delete_time), 
                "author": file_obj.author, 
                "album": file_obj.album, 
                "subject": file_obj.subject, 
                "hls_addr": file_obj.hls_addr, 
                "thumbnail_addr": file_obj.thumbnail_addr,
                "source_addr": file_obj.source_addr, 
                "status": file_obj.status,
                "remark": file_obj.remark
            }
            
            # 使用 md5 作为键，file_obj_json 作为值存入缓存
            cache.set(file_obj.md5, file_obj_data, timeout=60*60*24)  # 设置缓存过期时间为 24 小时
        
        return JsonResponse({"status": "加载成功", "count": len(file_objs)})
    except Exception as e:
        logger.error(f"加载数据到缓存时出错: {str(e)}")
        return JsonResponse({"status": "加载失败", "count": 0})

# 分类/标签管理
def manage_appertain(request, pk=None):
    ct = get_object_or_404(FileAppertain, pk=pk) if pk else None
    response_data = {}
    
    if request.method == "POST":
        form = FileAppertainForm(request.POST, instance=ct)
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
                
        elif "delete" in request.POST and ct:
            try:
                ct.delete()
                response_data['status'] = 'success'
                response_data['message'] = '删除成功！'
            except Exception as e:
                response_data['status'] = 'error'
                response_data['message'] = f'删除失败：{str(e)}'
        
        return JsonResponse(response_data)

    else:
        form = FileAppertainForm(instance=ct)

    # 查询所有分类
    appertains = FileAppertain.objects.filter(flag="C")
    # 如果没有发生错误，返回信息
    return render(request, 'files/ct.html', {
        'form': form,
        'appertains': appertains,
        'current_appertain': ct
    })

# 获取文件对象
def get_file_objs(request):
    try:
        file_info_list = FileInfo.objects.all().order_by('-created_time')
    except Exception as e:
        logger.error(f"获取文件列表时出错: {str(e)}")
        file_info_list = FileInfo.objects.none()  # 遇到错误时返回空查询集
    
    paginator = Paginator(file_info_list, 20)  # 每页显示20个文件
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'files/list.html', {'page_obj': page_obj})

# 获取remark为🔥的文件，并按🔥的数量进行排序
def get_hot_file_objs(request):
    try:
        # 获取所有remark包含🔥的文件对象
        hot_files = FileInfo.objects.filter(remark__contains='🔥')
        
        paginator = Paginator(hot_files, 20)  # 每页显示20个文件
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, 'files/search.html', {'page_obj': page_obj})
    except Exception as e:
        logger.error(f"获取热门文件时出错: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '获取热门文件失败'}, status=500)

# 获取remark为☆的文件，并按☆的数量进行排序
def get_favorites_file_objs(request):
    try:
        # 获取所有remark为☆的文件对象
        favorites_files = FileInfo.objects.filter(remark__contains='☆')
        
        paginator = Paginator(favorites_files, 20)  # 每页显示20个文件
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, 'files/search.html', {'page_obj': page_obj})
    except Exception as e:
        logger.error(f"获取收藏文件时出错: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '获取收藏文件失败'}, status=500)

# 获取已删除文件对象
def trash_file_objs(request):
    try:
        file_info_list = FileInfo.objects.filter(status__icontains="delete")
    except Exception as e:
        logger.error(f"获取删除文件列表时出错: {str(e)}")
        file_info_list = FileInfo.objects.none()  # 遇到错误时返回空查询集
    
    paginator = Paginator(file_info_list, 20)  # 每页显示15个文件
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'files/trash.html', {'page_obj': page_obj})

# 上传文件页
def upload(request):
    try:
        categories = FileAppertain.objects.filter(flag="C")
    except Exception as e:
        categories = []  # 错误情况下使用空列表
    return render(request, 'files/upload.html', {'categories': categories})

#上传目录文件页
def upload_dir(request):
    try:
        categories = FileAppertain.objects.filter(flag="C")
    except Exception as e:
        categories = []  # 错误情况下使用空列表
    return render(request, 'files/upload_dir.html', {'categories': categories})

# 视频流转换页
def v2hls(request):
    return render(request, 'files/v2hls.html')

# 查询文件
def search(request):
    try:
        # 获取前端查询内容
        search_term = request.GET.get('searchFiles', '')
        # 获取数据库中的所有文件数据
        files = FileInfo.objects.all().order_by('-created_time')  
        # 如果查询内容存在，则进行过滤
        if search_term:
            files = files.filter(Q(name__icontains=search_term) | Q(md5__icontains=search_term) | Q(album__icontains=search_term) | Q(subject__icontains=search_term) | Q(remark__icontains=search_term))

        # 分页展示查询数据
        paginator = Paginator(files, 20)  # 每页20个文件
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # 渲染页面
        return render(request, 'files/search.html', {'page_obj': page_obj})

    except Exception as e:
        logger.error(f"检索文件时出错，请检查！\n {str(e)}")
        # 如果发生异常，返回空查询集或其他适当的处理
        return render(request, 'files/search.html', {'page_obj': []})
    
# 获取文件数据，用以展示与下载
def get_file_data(request):
    """
    获取文件数据，用于展示与下载
    """
    try:
        # 获取并验证 md5 参数
        md5 = request.GET.get('md5')
        if not md5:
            return JsonResponse({'error': '缺少md5参数'}, status=400)
            
        # 首先尝试从缓存获取数据
        file_obj = cache.get(md5)

        if not file_obj:
            logger.warning(f"文件(MD:{md5})信息尚未被缓存, 现将从数据库中进行查询，请稍等......")
            # 缓存未命中，从数据库获取
            db_file = FileInfo.objects.filter(md5=md5).first()
            
            if not db_file:
                return JsonResponse({'error': '文件未找到'}, status=404)
                
            # 构建缓存数据
            file_obj = {
                "name": db_file.name,
                "code": db_file.code, 
                "size": str(db_file.size), 
                "type": db_file.type, 
                "mime": db_file.mime, 
                "wh": db_file.wh, 
                "level": db_file.level, 
                "data": db_file.data, 
                "created_time": str(db_file.created_time), 
                "delete_time": str(db_file.delete_time), 
                "author": db_file.author, 
                "album": db_file.album, 
                "subject": db_file.subject, 
                "hls_addr": db_file.hls_addr, 
                "thumbnail_addr": db_file.thumbnail_addr,
                "source_addr": db_file.source_addr, 
                "status": db_file.status,
                "remark": db_file.remark
            }
            # 设置缓存
            cache.set(md5, file_obj, timeout=60*60*24)

        # 确保 file_obj 是字典
        if isinstance(file_obj, FileInfo):
            file_obj = {
                "name": file_obj.name,
                "code": file_obj.code, 
                "size": str(file_obj.size), 
                "type": file_obj.type, 
                "mime": file_obj.mime, 
                "wh": file_obj.wh, 
                "level": file_obj.level, 
                "data": file_obj.data, 
                "created_time": str(file_obj.created_time), 
                "delete_time": str(file_obj.delete_time), 
                "author": file_obj.author, 
                "album": file_obj.album, 
                "subject": file_obj.subject, 
                "hls_addr": file_obj.hls_addr, 
                "thumbnail_addr": file_obj.thumbnail_addr,
                "source_addr": file_obj.source_addr, 
                "status": file_obj.status,
                "remark": file_obj.remark
            }

        # 处理文件数据
        file_data = json.loads(file_obj['data']) if isinstance(file_obj['data'], str) else file_obj['data']
        # 验证 HLS 地址
        hls_addr = file_obj.get('hls_addr')  # 使用 get 方法提供默认值
        if hls_addr and not os.path.exists(str(hls_addr)):
            hls_addr = None

        return JsonResponse({
            'fileName': file_obj['name'],
            'fileType': file_obj['type'],
            'fileWH': file_obj['wh'],
            'fileSize': file_obj['size'],
            'fileDatas': file_data,
            'hlsAddr': hls_addr,
            'status': file_obj['status']
        })
        
    except json.JSONDecodeError:
        logger.error(f"文件数据JSON解析错误: md5={md5}")
        return JsonResponse({'error': '文件数据格式错误'}, status=500)
    except Exception as e:
        logger.error(f"获取文件数据时出错: {str(e)}")
        return JsonResponse({'error': '服务器内部错误'}, status=500)

# 保存上传文件
def save_upload_files(request) -> JsonResponse:
    """处理文件上传请求
    Args:
        request: HTTP请求对象
    
    Returns:
        JsonResponse: 包含上传结果的JSON响应
    """
    if request.method != 'POST':
        categories = FileAppertain.objects.filter(flag="C")
        return render(request, 'files/upload.html', {'categories': categories})

    # 初始化上传结果
    upload_result = {"successful": [], "exist": [], "failed": []}

    # 验证文件
    files = request.FILES.getlist('file_field')
    if not files:
        return JsonResponse({'message': '没有上传文件，请检查......'}, status=400)

    # 获取并验证上传参数
    upload_params = {
        'album': request.POST.get('album', '').strip(),
        'subject': request.POST.get('subject', '').strip(),
        'level': request.POST.get('fileLevel'),
        'category_id': request.POST.get('fileCategory'),
        'tags': [tag.strip() for tag in request.POST.get('manyTags', '').split('/') if tag.strip()]
    }

    # 处理每个文件
    for file in files:
        try:
            file_md5 = get_md5(file)
            # 检查文件是否已存在
            if cache.get(file_md5):
                upload_result['exist'].append({'name': file.name, 'md5': file_md5})
                continue

            # 处理图片尺寸
            img_wh = {"w": None, "h": None}
            if file.content_type.startswith('image/'):
                img_wh['w'], img_wh['h'] = get_image_wh(file)

            # 处理上传文件
            file_dir = os.path.join('media', timezone.now().strftime('%Y-%m-%d'), file_md5)
            data = handle_uploaded_file(file, fileDir=file_dir)
            
            if not data:
                logger.error(f"保存文件出现错误，{file.name} (MD5:{file_md5})文件数据未能正确保存到服务端，请检查......")
                continue
                
            # 异步处理保存数据
            save_file_data.delay(
                file_name=file.name,
                file_md5=file_md5,
                mime=file.content_type,
                file_size=file.size,
                file_type=get_f_ext(file)['file_extension'],
                img_wh=img_wh,
                file_data=data,
                file_dir=file_dir,
                **upload_params
            )
            
            cache.set(file_md5, {
                'name': file.name,
                'md5': file_md5,
                'mime': file.content_type,
                'size': file.size,
                'type': get_f_ext(file)['file_extension'],
                'wh': img_wh,
                'album': upload_params['album'],
                'subject': upload_params['subject'],
                'level': upload_params['level'],
                'data': data,
                'source_addr': file_dir,
                'hls_addr': None,
                'status':'enable'
            }, timeout=60*60*24)
            
            upload_result['successful'].append({'name': file.name, 'md5': file_md5})
            
        # 如果上传错误
        except Exception as e:
            logger.error(f"处理文件 {file.name} (MD5:{file_md5}) 时出错: {str(e)}")
            upload_result['failed'].append({'name': file.name, 'md5': file_md5})

    # 返回最终结果
    return JsonResponse(upload_result)

# 更新文件信息
@require_POST
def update_file_info(request, md5):
    """
    更新文件信息，包括所有字段及分类/标签
    """
    try:
        # 使用事务确保数据一致性
        with transaction.atomic():
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
                # 提供详细的错误信息
                return JsonResponse({
                    "status": "error",
                    "content": "更新失败！",
                    "errors": form.errors.as_json()
                }, status=400)
    except Exception as e:
        logger.error(f"更新文件信息时出错: {str(e)}")
        return JsonResponse({
            "status": "error",
            "content": "服务器内部错误，请稍后重试。",
            "error": str(e)
        }, status=500)

# 删除文件
def delete_file(request):
    try:
        # 获取并验证 md5 参数
        md5 = request.GET.get('md5')
        if not md5:
            return JsonResponse({"status": "Failed", "content": "缺少md5参数"}, status=400)

        # Retrieve the file object or return a 404 if not found
        file_obj = get_object_or_404(FileInfo, md5=md5)

        # Determine the file directory based on source_addr or default path
        file_dir = file_obj.source_addr or os.path.join('media', file_obj.created_time.strftime('%Y-%m-%d'), file_obj.md5)

        # Ensure the directory exists before attempting to remove it
        if os.path.exists(file_dir):
            # 如果回收站不存在，则创建
            trash_dir = os.path.join('media', 'Trash')
            os.makedirs(trash_dir, exist_ok=True)
            # 将文件移动到回收站
            shutil.move(file_dir, os.path.join(trash_dir, file_obj.md5))

            try:
                with transaction.atomic():
                    file_obj.status = "deleted"
                    file_obj.save()
                logger.info(f"Successfully moved {file_obj.name}(MD5:{file_obj.md5}) to Trash: {file_dir}")
                return JsonResponse({"status": "Successful", "content": f"文件:{file_obj.name}(MD5:{file_obj.md5})源数据已成功删除！"})
            except Exception as e:
                logger.error(f"文件:{file_obj.name}(MD5:{file_obj.md5})删除中，数据状态更新为：'delete' 时出现错误：{e}")
                return JsonResponse({"status": "Failed", "content": f"文件：{file_obj.name}(MD5:{file_obj.md5})状态更新失败，请重试或联系工程师......"})

        else:
            logger.warning(f"file:{file_obj.name}(MD5:{file_obj.md5}) not found, 请检查......")
            return JsonResponse({"status": "Failed", "content": f"文件:{file_obj.name}(MD5:{file_obj.md5})源数据已不存在，请检查......"})

    except Exception as e:
        # Log the exception and return an error response
        logger.error(f"Error deleting file:{file_obj.name}(MD5:{file_obj.md5}): {e}")
        return JsonResponse({"status": "Failed", "content": f"删除文件:{file_obj.name}(MD5:{file_obj.md5})时出错，请联系工程师......"})

# 异步创建文件目录
async def make_dirs(path):
    """
    创建目录，如果目录已存在则不执行任何操作。

    参数:
        path (str): 要创建的目录路径
    """
    os.makedirs(path, exist_ok=True)  # 使用 os.makedirs 创建目录，exist_ok=True 表示如果目录已存在则不抛出异常

# 异步合并文件块到一个单一文件中
async def merge_file_blocks(file_path, data_list):
    """
    合并文件块到一个单一文件中。

    参数:
    file_path: str - 合并后文件的保存路径。
    data_list: list - 包含要合并的文件块路径的列表。
    """
    async with aiofiles.open(file_path, 'wb') as f:
        # 以写入模式打开目标文件，准备写入合并后的数据
        for data in data_list:
            async with aiofiles.open(data, 'rb') as cf:
                # 以读取模式打开每个文件块
                await f.write(await cf.read())
                # 读取文件块的内容并写入目标文件

# 将视频文件转为HLS流
async def vFile_to_HLS(request, md5):
    # 检查MD5值是否有效
    if not md5 or not isinstance(md5, str) or len(md5) != 32:
        return JsonResponse({"error": "输入的MD5值无效, 请检查......"}, status=400)

    try:
        # 启动异步任务并等待其结果
        await vFile_to_HLS_task(md5)
    except Exception as e:
        # 记录错误信息
        logger.error(f"启动视频转换任务时出错: {e}")
        return JsonResponse({"error": "视频转换任务启动失败"}, status=500)

    # 返回任务启动成功的响应
    return JsonResponse({"result": "视频流转换任务已启动，请稍等......"})

# 将传频文件转为HLS流
async def vFile_to_HLS_task(md5):
    # 获取 channel_layer，用于发送消息
    channel_layer = get_channel_layer()

    try:
        # 向 'chat_room' 组发送消息，开始处理视频文件
        await channel_layer.group_send(
            f"room_{md5}", 
            {
                'type': 'updata_task_status', 
                'status': '开始',
                'message': "开始处理视频文件，请稍等......",
            }
        )
        
        # 查询视频文件，检查是否存在
        exist_file = await sync_to_async(FileInfo.objects.filter(md5=md5).first)()

        if not exist_file:
            # 如果文件不存在，发送警告消息
            await channel_layer.group_send(
                f"room_{md5}", 
                {
                    'type': 'updata_task_status', 
                    'status': '警告',
                    'message': "需要转换的视频文件不存在，请检查！",
                }
            )
            logger.error(f"未找到MD5为 {md5} 的视频文件, 请检查......")
            return
        
        # 检查HLS流是否已存在
        if exist_file.hls_addr and os.path.exists(exist_file.hls_addr):
            await channel_layer.group_send(
                f"room_{md5}", 
                {
                    'type': 'updata_task_status', 
                    'status': '警告',
                    'message': "视频文件HLS流已存在，请检查！",
                }
            )
            logger.error(f"MD5为{md5}的视频文件HLS流已存在, 请检查!")
            return
        
        # 更新任务状态为处理中
        await channel_layer.group_send(
            f"room_{md5}",
            {
                'type': 'updata_task_status',
                'status': '处理中',
                'message': "HLS视频流正在生成，请稍等......",
            }
        )

        # 定义文件路径
        keyDir = os.path.join('media', 'VKey', timezone.now().strftime('%Y-%m-%d'), exist_file.md5)
        hlsDir = os.path.join('media', 'HLS', timezone.now().strftime('%Y-%m-%d'), exist_file.md5)
        vf_path = os.path.join(hlsDir, f"{exist_file.md5}.{exist_file.type}")

        # 创建必要的目录
        await make_dirs(keyDir)
        await make_dirs(hlsDir)

        # 合并文件块数据
        data_list = json.loads(exist_file.data)
        await merge_file_blocks(vf_path, data_list)

        # 生成视频流密钥
        keyInfo = await sync_to_async(generate_encryption_key)(keyDir)
        # 将视频转换为HLS流
        m3u8 = await sync_to_async(convert_to_encrypted_hls)(vf_path, hlsDir, keyInfo)

        # 保存HLS地址到数据库
        exist_file.hls_addr = m3u8
        await sync_to_async(exist_file.save)()

        # 清理合成文件
        if os.path.exists(vf_path):
            os.remove(vf_path)
        
        # 更新任务完成状态
        await channel_layer.group_send(
            f"room_{md5}", 
            {
                'type': 'updata_task_status', 
                'status': '已完成',
                'message': "视频文件成功转换为HLS流！",
            }
        )
    
    except Exception as e:
        # 处理异常，发送任务失败消息
        await channel_layer.group_send(
            f"room_{md5}", 
            {
                'type': 'updata_task_status',
                'status': '任务失败',
                'message': "生成HLS视频流失败，请检查！",
            }
        )
        logger.error(f"处理视频文件 {md5} 时出现未知错误: {e}", exc_info=True)

# 测试websocket所用
async def test_send_message(request):
    if request.method == "POST":
        # 从查询参数中获取消息
        message = request.GET.get('message', '')
        if message:
            # 获取 channel_layer
            channel_layer = get_channel_layer()
            # 向 'chat_room' 组发送消息
            await channel_layer.group_send(
                "chat_chat_room", # 与你的消费者中的组名一致
                {
                    'type': 'test',  # 消息类型，通常由消费者处理
                    'message': "CCHHHHHHHHHHHHHHHHCC",  # 消息内容
                }
            )

            return JsonResponse({"status": "Message sent!"})
        return HttpResponseBadRequest("No message provided")
    return HttpResponseBadRequest("Invalid HTTP method")

# 随机处理页
def random_all(request):
    try:
        file_objs = FileInfo.objects.filter(status="enable").order_by('-created_time')
        # 提取所需字段，比如文件数据块地址
        file_objs_list = [{"id": file_obj.id, "name":file_obj.name, "md5":file_obj.md5, "album":file_obj.album, "subject":file_obj.subject, "data": file_obj.data, "hlsAddr":file_obj.hls_addr, "fileSize":float(file_obj.size), "mime":file_obj.mime, "wh":file_obj.wh, "remark":file_obj.remark} for file_obj in file_objs]
        file_objs_json = json.dumps(file_objs_list)  # 将列表转换为JSON格式
    except Exception as e:
        logger.error(f"获取文件列表时出错: {str(e)}")
        file_objs_json = json.dumps([])  # 返回空JSON数据

    return render(request, 'files/random.html', {'file_objs': file_objs_json})

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
        file_objs_list = [{"id": file_obj.id, "name":file_obj.name, "md5":file_obj.md5, "album":file_obj.album, "subject":file_obj.subject, "data": file_obj.data, "hlsAddr":file_obj.hls_addr, "fileSize":float(file_obj.size), "mime":file_obj.mime, "wh":file_obj.wh, "remark":file_obj.remark} for file_obj in file_objs]
        file_objs_json = json.dumps(file_objs_list)  # 将列表转换为JSON格式
        
    except Exception as e:
        logger.error(f"获取文件列表时出错: {str(e)}")
        file_objs_json = json.dumps([])  # 返回空JSON数据
    
    return render(request, 'files/random.html', {'file_objs': file_objs_json})