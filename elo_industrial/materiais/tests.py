from django.test import TestCase
from django.urls import reverse

from contas.tests import DADOS

from .models import Material

MATERIAL = {
    'intencao': 'oferta',
    'categoria': 'madeira',
    'titulo': 'Apara de madeira',
    'descricao': 'Sobra de MDF e pinus.',
    'quantidade': '300',
    'unidade': 'kg',
    'frequencia': 'semanal',
    'modalidade': 'venda',
    'preco': '0.50',
}


class MaterialTests(TestCase):
    def entrar(self, email='contato@boamadeira.com'):
        self.client.post(reverse('cadastro'), {**DADOS, 'email': email})

    def test_painel_exige_login(self):
        resp = self.client.get(reverse('painel'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('login'), resp.url)

    def test_cadastrar_material(self):
        self.entrar()
        resp = self.client.post(reverse('material_novo'), MATERIAL)
        self.assertRedirects(resp, reverse('painel'))
        self.assertEqual(Material.objects.get().titulo, 'Apara de madeira')

    def test_doacao_ignora_preco(self):
        self.entrar()
        self.client.post(reverse('material_novo'), {**MATERIAL, 'modalidade': 'doacao'})
        self.assertIsNone(Material.objects.get().preco)

    def test_home_e_detalhe_sao_publicos(self):
        self.entrar()
        self.client.post(reverse('material_novo'), MATERIAL)
        self.client.logout()
        self.assertContains(self.client.get(reverse('home')), 'Apara de madeira')
        m = Material.objects.get()
        self.assertEqual(self.client.get(reverse('material_detalhe', args=[m.pk])).status_code, 200)

    def test_outra_empresa_nao_edita_nem_exclui(self):
        self.entrar()
        self.client.post(reverse('material_novo'), MATERIAL)
        m = Material.objects.get()
        self.client.logout()
        self.entrar('outra@empresa.com')
        self.assertEqual(self.client.get(reverse('material_editar', args=[m.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('material_excluir', args=[m.pk])).status_code, 404)
        self.assertEqual(Material.objects.count(), 1)

    def test_excluir_material(self):
        self.entrar()
        self.client.post(reverse('material_novo'), MATERIAL)
        m = Material.objects.get()
        self.client.post(reverse('material_excluir', args=[m.pk]))
        self.assertEqual(Material.objects.count(), 0)
