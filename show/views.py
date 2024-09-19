from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator

# Create your views here.

def index(request):
    return render(request, 'show/index.html')