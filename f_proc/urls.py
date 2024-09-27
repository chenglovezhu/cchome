from django.urls import path, re_path
from . import views

urlpatterns = [
    path("random/", views.random_all, name="random"),
    path("myrandom/", views.random_filter, name="random_filter"),
    path("upload/", views.upload, name="upload"),
    path("upload_dir/", views.upload_dir, name="upload_dir"),
    path("upload_hls/", views.save_hls_data, name="save_hls_data"),
    path("list/", views.file_list, name="file_list"),
    path("recycleBin/", views.recycleBin, name="recycleBin"),
    path("data/<str:md5>/", views.get_file_data, name="get_file_data"),
    path("upload_files/", views.save_file_data, name="save_file_data"),
    path('ct/manage/', views.manage_appertain, name='manage_appertain'),
    path('ct/manage/<int:pk>/', views.manage_appertain, name='manage_appertain'),
    path("filter/", views.file_search, name="file_search"),
    path("v2hls/", views.v2hls, name="v2hls"),
    path("v2hls/<str:md5>/", views.vFile_to_HLS, name="vFile_to_HLS"),
    path('v2hls/status/<str:md5>/', views.v2hls_task_status_view, name='v2hls_task_status'),
    path("check/<str:md5>/", views.check_and_delete_file_chunks, name="check_and_delete"),
    path("delete/", views.delete, name="delete"),
    path("delete/<str:md5>/", views.delete_file, name="delete_file"),
    path("status/disable/<str:md5>/", views.set_file_status_disable, name="set_file_status_disable"),
    path("status/enable/<str:md5>/", views.set_file_status_enable, name="set_file_status_enable"),
    path("update/<str:md5>/", views.update_file_info, name="update_file_info"),
]