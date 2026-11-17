from django.contrib import admin

from .models import Mensagem, Negociacao, Recibo


class MensagemInline(admin.TabularInline):
    model = Mensagem
    extra = 0
    readonly_fields = ('autor', 'texto', 'sistema', 'criada_em')
    can_delete = False


@admin.register(Negociacao)
class NegociacaoAdmin(admin.ModelAdmin):
    list_display = ('material', 'proponente', 'status', 'quantidade', 'modalidade', 'atualizada_em')
    list_filter = ('status', 'modalidade')
    inlines = [MensagemInline]


@admin.register(Recibo)
class ReciboAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'fornecedora_nome', 'receptora_nome', 'material_titulo', 'valor_total', 'emitido_em')
