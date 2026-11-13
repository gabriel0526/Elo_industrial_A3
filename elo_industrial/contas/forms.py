from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

from .models import Empresa

User = get_user_model()

ESTADOS = [
    'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG',
    'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
]


class CadastroForm(forms.Form):
    """Cria o usuário (login por e-mail) e o perfil da empresa de uma vez."""

    nome = forms.CharField(label='Nome da empresa', max_length=120)
    email = forms.EmailField(label='E-mail')
    tipo = forms.ChoiceField(label='O que a empresa faz na plataforma', choices=Empresa.TIPOS)
    cidade = forms.CharField(max_length=80)
    estado = forms.ChoiceField(choices=[(e, e) for e in ESTADOS], initial='PE')
    telefone = forms.CharField(label='Telefone (opcional)', max_length=20, required=False)
    senha = forms.CharField(label='Senha', widget=forms.PasswordInput, min_length=8)
    senha2 = forms.CharField(label='Repita a senha', widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError('Já existe uma conta com esse e-mail.')
        return email

    def clean(self):
        dados = super().clean()
        if dados.get('senha') and dados.get('senha') != dados.get('senha2'):
            self.add_error('senha2', 'As senhas não são iguais.')
        return dados

    def salvar(self):
        dados = self.cleaned_data
        usuario = User.objects.create_user(
            username=dados['email'], email=dados['email'], password=dados['senha']
        )
        Empresa.objects.create(
            usuario=usuario,
            nome=dados['nome'],
            tipo=dados['tipo'],
            cidade=dados['cidade'],
            estado=dados['estado'],
            telefone=dados['telefone'],
        )
        return usuario


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='E-mail')

    def clean_username(self):
        return self.cleaned_data['username'].lower()
