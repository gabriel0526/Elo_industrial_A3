import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from negociacoes.models import Negociacao
from negociacoes.tests import TERMOS, criar_empresa, criar_material

from . import servico

COM_IA = override_settings(ANTHROPIC_API_KEY='chave-de-teste', IA_LIMITE_POR_HORA=30)


def resposta_ferramenta(dados):
    return SimpleNamespace(content=[SimpleNamespace(type='tool_use', input=dados)])


def resposta_texto(texto):
    return SimpleNamespace(content=[SimpleNamespace(type='text', text=texto)])


class LimparAnuncioTests(TestCase):
    def test_aceita_valores_validos(self):
        campos = servico.limpar_anuncio({
            'intencao': 'oferta', 'categoria': 'madeira', 'titulo': 'Apara de MDF',
            'quantidade': 300, 'unidade': 'kg', 'frequencia': 'semanal',
            'modalidade': 'venda', 'preco': 0.4,
        })
        self.assertEqual(campos['quantidade'], '300.00')
        self.assertEqual(campos['preco'], '0.40')
        self.assertEqual(campos['categoria'], 'madeira')

    def test_descarta_o_que_o_formulario_nao_aceitaria(self):
        campos = servico.limpar_anuncio({
            'intencao': 'troca', 'categoria': 'ouro', 'titulo': 'x' * 300,
            'quantidade': -5, 'unidade': 'litros', 'preco': 'caro', 'invadido': 'sim',
        })
        self.assertEqual(list(campos), ['titulo'])
        self.assertEqual(len(campos['titulo']), 100)

    def test_doacao_nao_tem_preco(self):
        campos = servico.limpar_anuncio({'modalidade': 'doacao', 'preco': 10, 'titulo': 'Retalhos'})
        self.assertNotIn('preco', campos)

    def test_resposta_que_nao_e_dicionario(self):
        self.assertEqual(servico.limpar_anuncio('lixo'), {})


@COM_IA
class ChamadaApiTests(TestCase):
    def test_extrair_anuncio_usa_ferramenta_obrigatoria_e_modelo_configurado(self):
        cliente = MagicMock()
        cliente.messages.create.return_value = resposta_ferramenta(
            {'intencao': 'oferta', 'categoria': 'madeira', 'titulo': 'Apara de MDF', 'quantidade': 300}
        )
        with patch.object(servico, '_cliente', return_value=cliente):
            campos = servico.extrair_anuncio('tenho 300 kg de MDF')
        pedido = cliente.messages.create.call_args.kwargs
        self.assertEqual(pedido['tool_choice'], {'type': 'tool', 'name': 'preencher_anuncio'})
        self.assertEqual(pedido['model'], 'claude-haiku-5-5')
        self.assertIn('<descricao_da_pessoa>', pedido['messages'][0]['content'])
        self.assertEqual(campos['quantidade'], '300.00')

    def test_resposta_sem_campos_validos_vira_erro(self):
        cliente = MagicMock()
        cliente.messages.create.return_value = resposta_ferramenta({'categoria': 'ouro'})
        with patch.object(servico, '_cliente', return_value=cliente):
            with self.assertRaises(servico.IAErro):
                servico.extrair_anuncio('qualquer coisa')

    def test_erro_de_autenticacao_da_api_vira_erro_amigavel(self):
        import anthropic

        cliente = MagicMock()
        cliente.messages.create.side_effect = anthropic.AuthenticationError(
            'x', response=MagicMock(status_code=401, headers={}), body=None
        )
        with patch.object(servico, '_cliente', return_value=cliente):
            with self.assertRaisesMessage(servico.IAErro, 'chave da API'):
                servico.extrair_anuncio('qualquer coisa aqui')

    @override_settings(ANTHROPIC_API_KEY='')
    def test_sem_chave_fica_indisponivel(self):
        self.assertFalse(servico.disponivel())
        with self.assertRaises(servico.IAIndisponivel):
            servico._cliente()


@COM_IA
class MensagemServicoTests(TestCase):
    def setUp(self):
        self.marcenaria = criar_empresa('marcenaria')
        self.briquete = criar_empresa('briquete', cidade='Olinda')
        self.marcenaria.telefone = '81 99999-1234'
        self.marcenaria.save()
        self.oferta = criar_material(self.marcenaria)
        self.client.force_login(self.briquete.usuario)
        self.client.post(reverse('negociacao_nova', args=[self.oferta.pk]), {**TERMOS, 'mensagem': 'Olá!'})
        self.neg = Negociacao.objects.get()

    def test_contexto_tem_termos_e_conversa_mas_nao_dados_de_contato(self):
        contexto = servico.montar_contexto_negociacao(self.neg, self.briquete, 'pedir desconto')
        self.assertIn('Apara de madeira', contexto)
        self.assertIn('100 kg', contexto)
        self.assertIn('briquete: Olá!', contexto)
        self.assertIn('pedir desconto', contexto)
        self.assertNotIn('99999', contexto)
        self.assertNotIn('@teste.com', contexto)

    def test_texto_da_ia_e_limpo_e_limitado(self):
        cliente = MagicMock()
        cliente.messages.create.return_value = resposta_texto('"' + 'a' * 2000 + '"')
        with patch.object(servico, '_cliente', return_value=cliente):
            texto = servico.sugerir_mensagem(self.neg, self.briquete)
        self.assertEqual(len(texto), 1000)
        self.assertFalse(texto.startswith('"'))


@COM_IA
class ViewsIaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.marcenaria = criar_empresa('marcenaria')
        self.briquete = criar_empresa('briquete', cidade='Olinda')
        self.intrusa = criar_empresa('intrusa')
        self.oferta = criar_material(self.marcenaria)

    def post(self, nome, corpo, args=None):
        return self.client.post(
            reverse(nome, args=args or []), json.dumps(corpo), content_type='application/json'
        )

    def abrir_negociacao(self):
        self.client.force_login(self.briquete.usuario)
        self.client.post(reverse('negociacao_nova', args=[self.oferta.pk]), {**TERMOS, 'mensagem': ''})
        return Negociacao.objects.get()

    # ---- preencher material ----
    def test_exige_login(self):
        resp = self.post('ia_material', {'texto': 'tenho 300 kg de MDF por semana'})
        self.assertEqual(resp.status_code, 401)

    def test_somente_post(self):
        self.client.force_login(self.marcenaria.usuario)
        self.assertEqual(self.client.get(reverse('ia_material')).status_code, 405)

    @patch('ia.views.servico.extrair_anuncio', return_value={'categoria': 'madeira', 'titulo': 'MDF'})
    def test_preenche_material(self, extrair):
        self.client.force_login(self.marcenaria.usuario)
        resp = self.post('ia_material', {'texto': 'tenho 300 kg de MDF por semana'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['campos']['categoria'], 'madeira')
        extrair.assert_called_once()

    def test_texto_curto_ou_longo_demais(self):
        self.client.force_login(self.marcenaria.usuario)
        self.assertEqual(self.post('ia_material', {'texto': 'MDF'}).status_code, 400)
        self.assertEqual(self.post('ia_material', {'texto': 'a' * 1001}).status_code, 400)

    @override_settings(ANTHROPIC_API_KEY='')
    def test_sem_chave_devolve_503(self):
        self.client.force_login(self.marcenaria.usuario)
        self.assertEqual(self.post('ia_material', {'texto': 'tenho 300 kg de MDF'}).status_code, 503)

    @patch('ia.views.servico.extrair_anuncio', side_effect=servico.IAErro('falhou'))
    def test_erro_da_ia_vira_502_com_mensagem(self, _):
        self.client.force_login(self.marcenaria.usuario)
        resp = self.post('ia_material', {'texto': 'tenho 300 kg de MDF'})
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.json()['erro'], 'falhou')

    @override_settings(IA_LIMITE_POR_HORA=2)
    @patch('ia.views.servico.extrair_anuncio', return_value={'titulo': 'MDF'})
    def test_limite_por_hora(self, _):
        self.client.force_login(self.marcenaria.usuario)
        corpo = {'texto': 'tenho 300 kg de MDF'}
        self.assertEqual(self.post('ia_material', corpo).status_code, 200)
        self.assertEqual(self.post('ia_material', corpo).status_code, 200)
        self.assertEqual(self.post('ia_material', corpo).status_code, 429)

    # ---- mensagem ----
    @patch('ia.views.servico.sugerir_mensagem', return_value='Podemos fechar por R$ 0,42/kg?')
    def test_participante_recebe_sugestao(self, sugerir):
        neg = self.abrir_negociacao()
        resp = self.post('ia_mensagem', {'instrucao': 'pedir desconto'}, [neg.pk])
        self.assertEqual(resp.json()['texto'], 'Podemos fechar por R$ 0,42/kg?')
        self.assertEqual(sugerir.call_args.args[2], 'pedir desconto')

    @patch('ia.views.servico.sugerir_mensagem')
    def test_quem_nao_participa_recebe_404(self, sugerir):
        neg = self.abrir_negociacao()
        self.client.force_login(self.intrusa.usuario)
        resp = self.post('ia_mensagem', {}, [neg.pk])
        self.assertEqual(resp.status_code, 404)
        sugerir.assert_not_called()

    @patch('ia.views.servico.sugerir_mensagem')
    def test_negociacao_encerrada_nao_gera_sugestao(self, sugerir):
        neg = self.abrir_negociacao()
        neg.encerrar(self.briquete)
        resp = self.post('ia_mensagem', {}, [neg.pk])
        self.assertEqual(resp.status_code, 400)
        sugerir.assert_not_called()

    # ---- páginas ----
    def test_botao_aparece_com_ia_ativa(self):
        self.client.force_login(self.marcenaria.usuario)
        self.assertContains(self.client.get(reverse('material_novo')), 'Preencher com IA')
        neg = self.abrir_negociacao()
        self.assertContains(self.client.get(reverse('negociacao_detalhe', args=[neg.pk])), 'Sugerir mensagem com IA')

    @override_settings(ANTHROPIC_API_KEY='', DEBUG=True)
    def test_botao_some_sem_chave(self):
        self.client.force_login(self.marcenaria.usuario)
        resp = self.client.get(reverse('material_novo'))
        self.assertNotContains(resp, 'Preencher com IA')
        self.assertContains(resp, 'ANTHROPIC_API_KEY')  # dica só em modo de desenvolvimento
