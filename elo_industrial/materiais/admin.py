from django.contrib import admin

from .models import Material


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'empresa', 'intencao', 'categoria', 'quantidade', 'unidade', 'ativo')
    list_filter = ('intencao', 'categoria', 'modalidade', 'ativo')
    search_fields = ('titulo', 'empresa__nome')
