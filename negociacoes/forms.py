from django import forms

from .models import Negociacao


class TermosForm(forms.ModelForm):
    """Termos da negociação: quantidade, preço, modalidade e logística."""

    class Meta:
        model = Negociacao
        fields = ['quantidade', 'preco', 'modalidade', 'retirada']

    def __init__(self, *args, material, **kwargs):
        super().__init__(*args, **kwargs)
        self.material = material
        unidade = material.get_unidade_display()
        self.fields['quantidade'].label = f'Quantidade ({unidade})'
        self.fields['preco'].label = f'Preço por {unidade} (R$)'
        self.fields['preco'].help_text = 'Deixe em branco se for doação.'

    def clean_quantidade(self):
        qtd = self.cleaned_data['quantidade']
        if qtd <= 0:
            raise forms.ValidationError('Informe uma quantidade maior que zero.')
        # anúncio de entrega única: não dá para propor mais do que existe
        if self.material.frequencia == 'unica' and qtd > self.material.quantidade:
            raise forms.ValidationError(
                f'O anúncio tem só {self.material.quantidade.normalize():f} '
                f'{self.material.get_unidade_display()} disponíveis.'
            )
        return qtd

    def clean(self):
        dados = super().clean()
        if dados.get('modalidade') == 'doacao':
            dados['preco'] = None
        elif dados.get('modalidade') == 'venda' and not dados.get('preco'):
            self.add_error('preco', 'Informe o preço por unidade para uma venda.')
        elif dados.get('preco') is not None and dados['preco'] < 0:
            self.add_error('preco', 'O preço não pode ser negativo.')
        return dados


class PropostaForm(TermosForm):
    """Primeira proposta: termos + mensagem opcional."""

    mensagem = forms.CharField(
        label='Mensagem para a outra empresa (opcional)',
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={'rows': 3}),
    )


class MensagemForm(forms.Form):
    texto = forms.CharField(
        label='Mensagem', max_length=1000, widget=forms.Textarea(attrs={'rows': 3})
    )
