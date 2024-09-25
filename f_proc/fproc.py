import os
import json
import hashlib
import uuid
import subprocess
import logging
from PIL import Image
from django.db import connection

# 设置日志，记录系统运行错误信息
logger = logging.getLogger("f_proc")


def get_f_ext(f):
    try:
        file_name, file_extension = os.path.splitext(f.name)
        return {"file_name": file_name, "file_extension": file_extension}
    except Exception as e:
        logger.error(f"处理扩展名出错，请检查：: {str(e)}")
        return {"file_name": "unknown", "file_extension": "unknown"}
    
def get_md5(f):
    try:
        md5_hash = hashlib.md5()
        for chunk in f.chunks():
            md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        logger.error(f"获取文件MD5时，出现错: {str(e)}")

def get_image_wh(file):
    # 打开文件对象
    image = Image.open(file)
    width, height = image.size
    return width, height

def reset_auto_increment():
    try:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE file_info AUTO_INCREMENT = 1;")
        connection.commit()  # 提交事务
    except Exception as e:
        logger.error(f"重置数据ID出错，请检查，错误信息: {e}")
        
def replace_in_list(data, old_value, new_value):
    return [item.replace(old_value, new_value) if isinstance(item, str) else item for item in data]

def get_codec_info(input_video):
    # 检查输入视频文件是否存在
    if not os.path.isfile(input_video):
        logger.error(f"输入视频文件未找到: {input_video}")
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
    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe 错误: {e.stderr}")
        raise RuntimeError("无法获取视频编解码信息")
    except json.JSONDecodeError:
        raise ValueError("无法解析 FFprobe 输出的 JSON 信息")
    except subprocess.TimeoutExpired:
        raise TimeoutError("获取编解码信息超时")

    # 默认值设置
    video_codec = None
    audio_codec = None
    bit_rate = None
    r_frame_rate = None
    w, h = None, None

    # 提取编解码信息
    for stream in codec_info.get('streams', []):
        if stream.get('codec_type') == 'video':
            video_codec = stream.get('codec_name')
            bit_rate = stream.get('bit_rate')
            r_frame_rate = stream.get('r_frame_rate')
            w, h = stream.get('width'), stream.get('height')
        elif stream.get('codec_type') == 'audio':
            audio_codec = stream.get('codec_name')

    # 处理帧率（如果存在的话，将分数格式的帧率转为浮点数）
    if r_frame_rate:
        try:
            num, denom = map(int, r_frame_rate.split('/'))
            r_frame_rate = num / denom
        except ValueError:
            logger.error(f"无法解析帧率: {r_frame_rate}")
            r_frame_rate = None
    
    return video_codec, audio_codec, bit_rate, r_frame_rate, w, h

def generate_encryption_key(save_dir):
    # 检查输出目录是否存在
    if not os.path.isdir(save_dir):
        raise FileNotFoundError(f"输出目录未找到: {save_dir}")

    # 生成 AES-128 加密密钥
    key = os.urandom(16)  # 生成16字节的随机密钥
    iv = "694509a518656f5b098960d37fbe39c7"  # 可以根据需求生成随机IV
    
    encry_key = os.path.join(save_dir, 'encrypt.key')
    key_info = os.path.join(save_dir, 'key.keyinfo')
    
    try:
        with open(encry_key, 'wb') as f:
            f.write(key)
        
        # 创建密钥信息文件，FFmpeg 需要这个文件来加密视频
        content = f"http://127.0.0.1:8888/{encry_key}\n{encry_key}\n{iv}"
        
        with open(key_info, 'w') as f:
            f.write(content)
            
    except IOError as e:
        logger.error(f"写入密钥文件时出错: {e}")
        raise
    
    return key_info

def convert_to_encrypted_hls(input_video, output_dir, key_info):
    # 检查输出目录是否存在
    if not os.path.isdir(output_dir):
        raise FileNotFoundError(f"输出目录未找到: {output_dir}")

    # 获取视频和音频的编码信息
    video_codec, audio_codec, bit_rate, r_frame_rate, w, h = get_codec_info(input_video)
    
    # 构建 FFmpeg 命令
    ffmpeg_command = ['ffmpeg', '-i', input_video]
    
    # 检查视频是否符合 HLS 要求
    if video_codec == 'h264':
        ffmpeg_command.extend(['-c:v', 'copy'])  # 视频编码符合，直接复制
    else:
        ffmpeg_command.extend(['-c:v', 'libx264'])  # 视频编码不符合，进行转换
        if bit_rate:
            ffmpeg_command.extend(['-b:v', bit_rate])  # 设置视频比特率
        if r_frame_rate:
            ffmpeg_command.extend(['-r', r_frame_rate])  # 设置视频帧率
    
    if audio_codec == 'aac':
        ffmpeg_command.extend(['-c:a', 'copy'])  # 音频编码符合，直接复制
    else:
        ffmpeg_command.extend(['-c:a', 'aac'])  # 音频编码不符合，进行转换
    
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
        return w, h, os.path.join(output_dir, 'playlist.m3u8')
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg 错误: {e.stderr}")
        raise RuntimeError("FFmpeg 处理失败")
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg 处理超时")
        raise TimeoutError("FFmpeg 处理超时")