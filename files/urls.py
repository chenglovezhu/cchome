from django.urls import path
from . import views

urlpatterns = [
    # 加载数据
    path("load_data/", views.load_data_to_cache, name="load_data"),   #查询相关文件信息
    
    # 分类/标签管理
    path('ct/manage/', views.manage_appertain, name='manage_appertain'),
    path('ct/manage/<int:pk>/', views.manage_appertain, name='manage_appertain'),
    
    # 查询文件
    path("search/", views.search, name="search_file_objs"),   #查询相关文件信息
    path("list/", views.get_file_objs, name="get_file_objs"),   #查询所有文件信息
    path("hot/", views.get_hot_file_objs, name="get_hot_file_objs"),   #查询火热文件信息
    path("favorites/", views.get_favorites_file_objs, name="get_favorites_file_objs"),   #查询收藏文件信息
    path("trash/", views.trash_file_objs, name="trash_file_objs"),   #查询所有删除文件信息
    path("data/", views.get_file_data, name="get_file_data"),    #通过文件md5查询到文件数据块
    
    # 获取文件，用作随机展示
    path("random/", views.random_all, name="random"),   #随机返回文件对象
    path("myrandom/", views.random_filter, name="random_filter"),   #按条件返加文件对象列表
    
    # 上传文件
    path("upload/", views.upload, name="upload"), 
    path("upload_dir/", views.upload_dir, name="upload_dir"),
    path("save_files/", views.save_upload_files, name="save_files"),
    
    # 视频流转换
    path("v2hls/", views.v2hls, name="v2hls"), 
    path("v2hls/<str:md5>/", views.vFile_to_HLS, name="vFile_to_HLS"),
    
    # 更新文件数据
    path("update/<str:md5>/", views.update_file_info, name="update_file_info"),
    
    # 删除文件信息
    path("delete/", views.delete_file, name="delete_file"),

    # 测试所用
    path('send_message/',views.test_send_message, name='test_send_message'),
]