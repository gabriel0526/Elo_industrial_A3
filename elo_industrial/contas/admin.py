from django.contrib import admin

from .models import Empresa


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'cidade', 'estado', 'criada_em')
    list_filter = ('tipo', 'estado')
    search_fields = ('nome', 'usuario__email')
