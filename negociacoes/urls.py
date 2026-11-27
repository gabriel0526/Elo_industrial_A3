from django.urls import path

from . import views

urlpatterns = [
    path('negociacoes/', views.lista, name='negociacoes_lista'),
    path('negociacoes/ao-vivo/', views.ao_vivo, name='ao_vivo'),
    path('negociacoes/<int:pk>/ao-vivo/', views.ao_vivo_negociacao, name='negociacao_ao_vivo'),
    path('materiais/<int:material_pk>/propor/', views.nova, name='negociacao_nova'),
    path('negociacoes/<int:pk>/', views.detalhe, name='negociacao_detalhe'),
    path('negociacoes/<int:pk>/alterar/', views.alterar, name='negociacao_alterar'),
    path('negociacoes/<int:pk>/mensagem/', views.mensagem, name='negociacao_mensagem'),
    path('negociacoes/<int:pk>/aceitar/', views.aceitar, name='negociacao_aceitar'),
    path('negociacoes/<int:pk>/encerrar/', views.encerrar, name='negociacao_encerrar'),
    path('negociacoes/<int:pk>/confirmar/', views.confirmar, name='negociacao_confirmar'),
    path('recibos/<int:pk>/', views.recibo, name='recibo'),
    path('resultados/', views.resultados, name='resultados'),
    path('resultados/exportar/', views.resultados_exportar, name='resultados_exportar'),
]
