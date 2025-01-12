0、python manage.py makemigrations app   python manage.py migrate

1、start project : python manage.py collectstatic && python manage.py runserver

2、start celery : celery -A pv worker

3、daphne pv.asgi:application -p 8899