# 使用官方 Python 镜像作为基础镜像
FROM python:3.12.6-slim-bullseye

# 将默认的源更换为速度更快的本地镜像源
RUN sed -i 's|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' /etc/apt/sources.list
# 安装 netcat 工具
RUN apt-get update && apt-get install -y netcat-openbsd ffmpeg

# 设置工作目录
WORKDIR /app

# 复制项目的依赖文件 requirements.txt 到容器中
COPY requirements.txt /app/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个项目到容器中
COPY . /app/

# # 运行 Django 数据库迁移
# RUN python manage.py makemigrations f_proc
# RUN python manage.py migrate f_proc

# 启动命令，启动 Django 开发服务器
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]