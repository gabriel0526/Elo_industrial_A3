from django import forms

from .models import Material


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = [
            'intencao', 'categoria', 'titulo', 'descricao', 'quantidade',
            'unidade', 'frequencia', 'modalidade', 'preco', 'foto',
        ]
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}

    def clean(self):
        dados = super().clean()
        # doação não tem preço
        if dados.get('modalidade') == 'doacao':
            dados['preco'] = None
        return dados


class FiltroForm(forms.Form):
    """Filtros da página de busca (todos opcionais, enviados por GET)."""

    ORDENS = [
        ('recentes', 'Mais recentes'),
        ('proximos', 'Mais próximos de mim'),
    ]

    q = forms.CharField(label='Buscar por palavra', required=False)
    intencao = forms.ChoiceField(
        label='Tipo de anúncio',
        required=False,
        choices=[('', 'Ofertas e procuras')] + Material.INTENCOES,
    )
    categoria = forms.ChoiceField(
        required=False, choices=[('', 'Todas as categorias')] + Material.CATEGORIAS
    )
    modalidade = forms.ChoiceField(
        required=False, choices=[('', 'Qualquer modalidade')] + Material.MODALIDADES
    )
    cidade = forms.CharField(required=False)
    estado = forms.CharField(required=False, max_length=2)
    ordem = forms.ChoiceField(label='Ordenar por', required=False, choices=ORDENS)
