   构建docker镜像：docker build -t ccfiles:v1.1.* .
   启动项目：docker-compose -f pv.yaml up -d

0、python manage.py makemigrations app   python manage.py migrate

1、start project : python manage.py collectstatic && python manage.py runserver

2、start celery : celery -A pv worker

3、daphne pv.asgi:application -p 8899