"""
URL configuration for PAV project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from f_proc import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('files/', include("f_proc.urls")),
    path('user/', include("user.urls")),
    path('', include("show.urls")),
]

# 配置自定义的 404 处理视图
handler404 = 'f_proc.views.custom_404_view'