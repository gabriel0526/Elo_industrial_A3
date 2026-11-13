from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('materiais/', views.buscar, name='buscar'),
    path('painel/', views.painel, name='painel'),
    path('materiais/novo/', views.material_novo, name='material_novo'),
    path('materiais/<int:pk>/', views.material_detalhe, name='material_detalhe'),
    path('materiais/<int:pk>/editar/', views.material_editar, name='material_editar'),
    path('materiais/<int:pk>/excluir/', views.material_excluir, name='material_excluir'),
]
