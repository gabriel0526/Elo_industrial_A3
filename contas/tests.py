from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Empresa

DADOS = {
    'nome': 'Marcenaria Boa Madeira',
    'email': 'contato@boamadeira.com',
    'tipo': 'gerador',
    'cidade': 'Recife',
    'estado': 'PE',
    'telefone': '',
    'senha': 'senha-segura-123',
    'senha2': 'senha-segura-123',
}


class CadastroTests(TestCase):
    def test_cadastro_cria_usuario_e_empresa_e_faz_login(self):
        resp = self.client.post(reverse('cadastro'), DADOS)
        self.assertRedirects(resp, reverse('painel'))
        self.assertEqual(Empresa.objects.count(), 1)
        self.assertEqual(Empresa.objects.get().nome, 'Marcenaria Boa Madeira')
        self.assertIn('_auth_user_id', self.client.session)

    def test_email_repetido_e_recusado(self):
        self.client.post(reverse('cadastro'), DADOS)
        self.client.logout()
        resp = self.client.post(reverse('cadastro'), DADOS)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Já existe uma conta com esse e-mail.')

    def test_senhas_diferentes_sao_recusadas(self):
        resp = self.client.post(reverse('cadastro'), {**DADOS, 'senha2': 'outra-coisa-123'})
        self.assertContains(resp, 'As senhas não são iguais.')
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_login_por_email(self):
        self.client.post(reverse('cadastro'), DADOS)
        self.client.logout()
        resp = self.client.post(
            reverse('login'), {'username': 'contato@boamadeira.com', 'password': DADOS['senha']}
        )
        self.assertRedirects(resp, reverse('painel'))
