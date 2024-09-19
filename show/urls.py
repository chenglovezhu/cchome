from django.urls import path, re_path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("favicon.ico", RedirectView.as_view(url="/static/f_proc/mds/favicon.ico")),
    
]