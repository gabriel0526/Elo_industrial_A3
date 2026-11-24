from django.urls import path

from . import views

urlpatterns = [
    path('manifest.webmanifest', views.manifesto, name='manifesto'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('offline/', views.offline, name='offline'),
]
