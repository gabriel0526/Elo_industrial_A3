from django.urls import path

from . import views

urlpatterns = [
    path('ia/material/', views.preencher_material, name='ia_material'),
    path('ia/negociacoes/<int:pk>/mensagem/', views.sugerir_mensagem, name='ia_mensagem'),
]
