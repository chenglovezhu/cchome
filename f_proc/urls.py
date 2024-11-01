from django.urls import path, re_path
from . import views

urlpatterns = [
    # 查询文件
    path("list/", views.file_list, name="file_list"),   #查询所有文件信息
    path("random/", views.random_all, name="random"),   #随机返回文件对象
    path("myrandom/", views.random_filter, name="random_filter"),   #按条件返加文件对象列表
    path("filter/", views.file_search, name="file_search"),     #按条件查询文件对象
    path("recycleBin/", views.recycleBin, name="recycleBin"),   #查询已删除的所有文件
    
    # 查询单个文件数据
    path("data/<str:md5>/", views.get_file_data, name="get_file_data"),
    
    #更新文件信息
    path("update/<str:md5>/", views.update_file_info, name="update_file_info"),
    path("status/disable/<str:md5>/", views.set_file_status_disable, name="set_file_status_disable"),
    path("status/enable/<str:md5>/", views.set_file_status_enable, name="set_file_status_enable"),
    
    #删除文件
    path("delete/", views.delete, name="delete"),
    path("delete/<str:md5>/", views.delete_file, name="delete_file"),
    
    # 上传文件
    path("upload/", views.index_upload, name="upload"),     #上传文件页面
    path("upload_dir/", views.upload_dir, name="upload_dir"),   #上传文件夹页面
    path("upload_hls/", views.save_hls_data, name="save_hls_data"),     #上传视频流页面
    path("upload_files/", views.save_file_data, name="save_file_data"),     #处理上传文件
    path("upload_disappeared_files/", views.upload_disappeared_files, name="upload_disappeared_files"),    #处理上传后非常规删除的文件
    
    # 处理视频流
    path("v2hls/", views.v2hls, name="v2hls"),
    path("v2hls/<str:md5>/", views.vFile_to_HLS, name="vFile_to_HLS"),      #处理视频，将其转换为视频流
    path('v2hls/status/<str:md5>/', views.v2hls_task_status_view, name='v2hls_task_status'),    #查询视频流转换进度
    
    # 处理分类/标签
    path('ct/manage/', views.manage_appertain, name='manage_appertain'),
    path('ct/manage/<int:pk>/', views.manage_appertain, name='manage_appertain'),
    
    # 校验文件数据
    path("check/<str:md5>/", views.check_and_delete_file_chunks, name="check_and_delete"),
    path("checkAllFile/", views.checkAllFile_by_time, name="checkAllFile_by_time"),     # 查询某个日期内文件数与数据库是否一致
]