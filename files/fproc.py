import os
import uuid
import json
import subprocess
import hashlib
import logging
from PIL import Image
from pathlib import Path
from django.db import connection
from asgiref.sync import sync_to_async
from .models import FileRelationship, FileAppertain, FileInfo

# 设置日志
logger = logging.getLogger("files")

def get_md5(f):
    try:
        md5_hash = hashlib.md5()
        for chunk in f.chunks():
            md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        logger.error(f"获取文件MD5时，出现错: {str(e)}")
        
def get_f_ext(f):
    try:
        file_name, file_extension = os.path.splitext(f.name)
        return {"file_name": file_name, "file_extension": file_extension}
    except Exception as e:
        logger.error(f"处理扩展名出错，请检查：: {str(e)}")
        return {"file_name": "unknown", "file_extension": "unknown"}

def get_image_wh(file):
    try:
        # 打开文件对象
        image = Image.open(file)
        width, height = image.size
        return width, height
    except:
        return None, None
    
def reset_auto_increment():
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE file_info AUTO_INCREMENT = 1;")
        cursor.execute("ALTER TABLE file_appertain AUTO_INCREMENT = 1;")
        cursor.execute("ALTER TABLE file_relationship AUTO_INCREMENT = 1;")
        
# 处理上传文件，并将数据写入本地
def handle_uploaded_file(file, fileDir):
    chunk_size = 1024 * 1024  # 1MB
    created_chunks = []  # 用于跟踪已创建的文件块

    try:
        # 使用 Path 对象确保目录存在
        fileDir = Path(fileDir)
        fileDir.mkdir(parents=True, exist_ok=True)
        
        # 写入文件块数据
        with file.open('rb') as f:
            while True:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break
                chunk_uuid = str(uuid.uuid4())
                chunk_path = os.path.join(fileDir, chunk_uuid)
                with open(chunk_path, 'wb') as chunk_file:
                    chunk_file.write(chunk_data)
                created_chunks.append(chunk_path)  # 记录已创建的文件块
        
        return json.dumps(created_chunks)
        
    except Exception as e:
        # 只删除本次操作创建的文件块
        for chunk_path in created_chunks:
            if os.path.exists(chunk_path):  # 添加条件表达式
                try:
                    os.remove(chunk_path)
                except Exception as del_err:
                    logger.error(f"删除文件块失败 {chunk_path}: {str(del_err)}")
        logger.error(f"上传文件出错，请检查：{str(e)}")
        
        return False
        
# 关联文件与分类/标签
def create_file_relationship(f_obj, cId=None, tName=None, flag='T', parent=0):
    if cId:
        file_appertain = FileAppertain.objects.get(id=cId)
    elif tName:
        file_appertain, created = FileAppertain.objects.get_or_create(name=tName, flag=flag, parent=parent)
    else:
        return  # 如果没有传入有效的 ID 或名称，则不进行操作

    # 创建 FileRelationship
    FileRelationship.objects.create(file_info=f_obj, file_appertain=file_appertain)
        
# 保存文件与分类/标签联系
def save_file_relationships(fileInfo, tagNames, categoryID):
    
    for tagName in tagNames:
        tagName = tagName.strip()
        if tagName:
            create_file_relationship(fileInfo, tName=tagName)

    if categoryID:
        create_file_relationship(fileInfo, cId=categoryID)

# 获取视频编码信息   
def get_codec_info(input_video):
    """
    获取指定视频文件的编解码信息，包括视频和音频的编码格式、比特率和帧率。

    参数:
    input_video (str): 输入视频文件的路径。

    返回:
    tuple: 包含视频编码、音频编码、比特率和帧率的元组。
           如果未找到相应的信息，则返回 None。
    
    异常:
    FileNotFoundError: 如果输入视频文件不存在。
    RuntimeError: 如果无法获取编解码信息或解析 FFprobe 输出时发生错误。
    """
    # 检查输入视频文件是否存在
    if not os.path.isfile(input_video):
        logger.error(f"获取视频文件编码信息时，视频文件未找到: {input_video}")
        raise FileNotFoundError(f"输入视频文件未找到: {input_video}")
    
    # 使用 FFmpeg 获取视频和音频的编解码信息
    ffprobe_command = [
        'ffprobe', '-v', 'error', '-show_entries',
        'stream=width,height,bit_rate,r_frame_rate,codec_name,codec_type,duration',
        '-of', 'json', input_video
    ]
    
    try:
        result = subprocess.run(ffprobe_command, capture_output=True, text=True, check=True, timeout=600)
        codec_info = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        logger.error(f"获取视频文件编码信息时，遇到错误: {str(e)}")
        raise RuntimeError("无法获取视频编解码信息，请检查......")

    # 提取编解码信息
    video_codec, audio_codec, bit_rate, r_frame_rate = None, None, None, None
    for stream in codec_info.get('streams', []):
        codec_type = stream.get('codec_type')
        if codec_type == 'video':
            video_codec = stream.get('codec_name')
            bit_rate = stream.get('bit_rate')
            r_frame_rate = stream.get('r_frame_rate')
        elif codec_type == 'audio':
            audio_codec = stream.get('codec_name')
    
    return video_codec, audio_codec, bit_rate, r_frame_rate

def generate_encryption_key(save_dir):
    """
    生成 AES-128 加密密钥并保存到指定目录。

    参数:
    save_dir (str): 密钥文件保存的目录。

    返回:
    str: 密钥信息文件的路径。

    异常:
    FileNotFoundError: 如果输出目录不存在。
    IOError: 如果写入密钥文件时发生错误。
    """
    # 检查输出目录是否存在
    if not os.path.isdir(save_dir):
        raise FileNotFoundError(f"视频加密密码输出目录未找到: {save_dir}")

    # 生成 AES-128 加密密钥和随机 IV
    key = os.urandom(16)  # 生成16字节的随机密钥
    iv = os.urandom(16).hex()  # 生成16字节的随机IV
    
    encry_key = os.path.join(save_dir, 'encrypt.key')
    key_info = os.path.join(save_dir, 'key.keyinfo')
    
    try:
        with open(encry_key, 'wb') as f:
            f.write(key)
        
        # 创建密钥信息文件，FFmpeg 需要这个文件来加密视频
        content = f"http://127.0.0.1:8888/{encry_key}\n{encry_key}\n{iv}"
        
        with open(key_info, 'w') as f:
            f.write(content)
            
    except Exception as e:
        logger.error(f"写入密钥文件时出错: {e}")
        raise
    
    return key_info

def convert_to_encrypted_hls(input_video, output_dir, key_info):
    # 检查输出目录是否存在
    if not os.path.isdir(output_dir):
        raise FileNotFoundError(f"HLS视频流输出目录未找到: {output_dir}")
    
    # 获取视频和音频的编码信息
    video_codec, audio_codec, bit_rate, r_frame_rate = get_codec_info(input_video)
    
    # 构建 FFmpeg 命令
    ffmpeg_command = ['ffmpeg', '-i', input_video]

    # 检查视频编码并加入对应编码器
    if video_codec != "h264":
        ffmpeg_command.extend(['-c:v', 'libx264'])  # 正确：直接添加字符串
        if bit_rate:
            ffmpeg_command.extend(['-b:v', bit_rate])  # 设置视频比特率
        if r_frame_rate:
            ffmpeg_command.extend(['-r', r_frame_rate])  # 设置视频帧率
    else:
        ffmpeg_command.extend(['-c:v', 'copy'])  # 使用原编码器

    # 检查音频编码并加入对应编码器
    if audio_codec != "aac":
        ffmpeg_command.extend(['-c:a', 'aac'])  # 使用 aac
    else:
        ffmpeg_command.extend(['-c:a', 'copy'])  # 使用原编码器

    # 设置 HLS 和加密参数
    ffmpeg_command.extend([
        '-hls_time', '10',  # 每个切片的时长（秒）
        '-hls_key_info_file', key_info,  # 加密密钥信息文件
        '-hls_playlist_type', 'vod',
        '-hls_segment_filename', os.path.join(output_dir, f"{str(uuid.uuid4())}%05d.ts"),  # 输出的切片文件
        os.path.join(output_dir, 'playlist.m3u8')  # 输出的播放列表文件
    ])
    
    # 运行 FFmpeg 命令
    try:
        # 使用 subprocess.run 运行 FFmpeg 命令，并捕获错误输出
        subprocess.run(ffmpeg_command, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, timeout=3600)
        return os.path.join(output_dir, 'playlist.m3u8')
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg 错误: {e.stderr}")
        raise RuntimeError(f"FFmpeg 处理失败: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise TimeoutError("FFmpeg 处理超时")