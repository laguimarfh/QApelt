from django.urls import path
from django.shortcuts import render
from . import views

urlpatterns = [
    path('', views.upload_file, name='upload_file'),
    path('success/', lambda request: render(request, 'peltloader/success.html'), name='success'),
]
