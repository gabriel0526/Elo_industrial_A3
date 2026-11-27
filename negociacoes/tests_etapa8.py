from django.test import Client, TestCase
from django.urls import reverse

from .models import Negociacao
from .tests import TERMOS, criar_empresa, criar_material


class BaseAoVivo(TestCase):
    """Duas empresas em dois navegadores diferentes (dois clientes, duas sessões)."""

    def setUp(self):
        self.marcenaria = criar_empresa('marcenaria')
        self.briquete = criar_empresa('briquete', cidade='Olinda')
        self.intrusa = criar_empresa('intrusa')
        self.oferta = criar_material(self.marcenaria)
        self.a = self.client                        # marcenaria
        self.b = Client()                           # briquete
        self.a.force_login(self.marcenaria.usuario)
        self.b.force_login(self.briquete.usuario)

    def briquete_propoe(self, mensagem=''):
        self.b.post(reverse('negociacao_nova', args=[self.oferta.pk]), {**TERMOS, 'mensagem': mensagem})
        return Negociacao.objects.get()

    def versao(self, cliente, neg):
        return cliente.get(reverse('negociacao_ao_vivo', args=[neg.pk])).json()['v']


class EndpointsTests(BaseAoVivo):
    def test_exigem_login_e_respondem_em_json(self):
        anonimo = Client()
        neg = self.briquete_propoe()
        for url in (reverse('ao_vivo'), reverse('negociacao_ao_vivo', args=[neg.pk])):
            resp = anonimo.get(url)
            self.assertEqual(resp.status_code, 401, url)
            self.assertEqual(resp.json(), {'erro': 'login'})

    def test_somente_get_e_nunca_vai_para_o_cache(self):
        neg = self.briquete_propoe()
        self.assertEqual(self.a.post(reverse('ao_vivo')).status_code, 405)
        self.assertEqual(self.a.post(reverse('negociacao_ao_vivo', args=[neg.pk])).status_code, 405)
        self.assertEqual(self.a.get(reverse('ao_vivo'))['Cache-Control'], 'no-store')

    def test_so_as_duas_empresas_enxergam_a_negociacao(self):
        neg = self.briquete_propoe()
        intrusa = Client()
        intrusa.force_login(self.intrusa.usuario)
        self.assertEqual(intrusa.get(reverse('negociacao_ao_vivo', args=[neg.pk])).status_code, 404)
        self.assertEqual(self.a.get(reverse('negociacao_ao_vivo', args=[neg.pk])).status_code, 200)
        self.assertEqual(self.a.get(reverse('negociacao_ao_vivo', args=[99999])).status_code, 404)

    def test_resposta_so_tem_versao_e_pendencias(self):
        neg = self.briquete_propoe()
        self.assertEqual(set(self.a.get(reverse('negociacao_ao_vivo', args=[neg.pk])).json()), {'v', 'pendencias'})
        self.assertEqual(set(self.a.get(reverse('ao_vivo')).json()), {'v', 'pendencias'})

    def test_versao_nao_muda_sem_novidade(self):
        neg = self.briquete_propoe()
        self.assertEqual(self.versao(self.a, neg), self.versao(self.a, neg))
        self.assertEqual(self.a.get(reverse('ao_vivo')).json(), self.a.get(reverse('ao_vivo')).json())


class DoisNavegadoresTests(BaseAoVivo):
    def test_proposta_nova_aparece_para_a_outra_empresa(self):
        antes = self.a.get(reverse('ao_vivo')).json()
        self.assertEqual(antes['pendencias'], 0)
        self.briquete_propoe()
        depois = self.a.get(reverse('ao_vivo')).json()
        self.assertEqual(depois['pendencias'], 1)          # o contador do menu sobe
        self.assertNotEqual(antes['v'], depois['v'])        # e a lista de negociações se atualiza

    def test_mensagem_da_outra_empresa_muda_a_versao_e_aparece_na_pagina(self):
        neg = self.briquete_propoe()
        antes = self.versao(self.a, neg)
        self.b.post(reverse('negociacao_mensagem', args=[neg.pk]), {'texto': 'Consigo buscar na sexta'})
        self.assertNotEqual(self.versao(self.a, neg), antes)
        self.assertContains(self.a.get(reverse('negociacao_detalhe', args=[neg.pk])), 'Consigo buscar na sexta')

    def test_aceite_muda_a_versao_nas_duas_pontas(self):
        neg = self.briquete_propoe()
        antes_b = self.versao(self.b, neg)
        self.a.post(reverse('negociacao_aceitar', args=[neg.pk]))
        self.assertNotEqual(self.versao(self.b, neg), antes_b)
        self.assertEqual(self.versao(self.a, neg), self.versao(self.b, neg))
        self.assertContains(self.b.get(reverse('negociacao_detalhe', args=[neg.pk])), 'Termos aceitos')

    def test_confirmacao_de_entrega_e_conclusao_aparecem_ao_vivo(self):
        neg = self.briquete_propoe()
        self.a.post(reverse('negociacao_aceitar', args=[neg.pk]))
        v = self.versao(self.b, neg)
        self.a.post(reverse('negociacao_confirmar', args=[neg.pk]))
        v2 = self.versao(self.b, neg)
        self.assertNotEqual(v, v2)
        self.b.post(reverse('negociacao_confirmar', args=[neg.pk]))
        self.assertNotEqual(self.versao(self.a, neg), v2)
        self.assertContains(self.a.get(reverse('negociacao_detalhe', args=[neg.pk])), 'Ver recibo')

    def test_contraproposta_gera_pendencia_para_quem_propos(self):
        neg = self.briquete_propoe()
        self.a.post(reverse('negociacao_alterar', args=[neg.pk]), {
            'quantidade': '50', 'preco': '0.50', 'modalidade': 'venda', 'retirada': 'fornecedora',
        })
        self.assertEqual(self.b.get(reverse('ao_vivo')).json()['pendencias'], 1)


class PaginaTemOsGanchosTests(BaseAoVivo):
    def test_detalhe_traz_trechos_que_o_script_troca_e_a_versao_atual(self):
        neg = self.briquete_propoe('Olá!')
        resp = self.a.get(reverse('negociacao_detalhe', args=[neg.pk]))
        for gancho in ('id="neg-painel"', 'id="neg-mensagens"', 'id="neg-compor"', 'id="neg-selo"',
                       'id="ao-vivo-ponto"', 'data-ao-vivo="negociacao"'):
            self.assertContains(resp, gancho)
        self.assertContains(resp, f'data-versao="{self.versao(self.a, neg)}"')
        self.assertContains(resp, 'data-id="')

    def test_formulario_de_mensagem_some_quando_encerra(self):
        neg = self.briquete_propoe()
        self.b.post(reverse('negociacao_encerrar', args=[neg.pk]))
        self.assertNotContains(self.a.get(reverse('negociacao_detalhe', args=[neg.pk])), 'id="neg-compor"')

    def test_lista_traz_o_bloco_atualizavel_com_a_versao(self):
        self.briquete_propoe()
        resp = self.a.get(reverse('negociacoes_lista'))
        self.assertContains(resp, 'id="lista-ao-vivo"')
        self.assertContains(resp, f'data-versao="{self.a.get(reverse("ao_vivo")).json()["v"]}"')

    def test_script_e_endereco_so_para_quem_esta_logado(self):
        anonimo = Client().get(reverse('home'))
        self.assertNotContains(anonimo, 'aovivo.js')
        self.assertNotContains(anonimo, 'ao-vivo-url')
        logado = self.a.get(reverse('home'))
        self.assertContains(logado, 'js/aovivo.js')
        self.assertContains(logado, f'content="{reverse("ao_vivo")}"')
        self.assertContains(logado, 'data-nav-negociacoes')
