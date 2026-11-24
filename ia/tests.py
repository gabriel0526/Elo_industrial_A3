import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from negociacoes.models import Negociacao
from negociacoes.tests import TERMOS, criar_empresa, criar_material

from . import servico

# os testes não podem depender do .env de quem roda: fixam todas as chaves e o provedor
SEM_IA = dict(ANTHROPIC_API_KEY='', GEMINI_API_KEY='', IA_PROVEDOR='')
COM_IA = override_settings(**{**SEM_IA, 'ANTHROPIC_API_KEY': 'chave-de-teste'}, IA_LIMITE_POR_HORA=30)
COM_GEMINI = override_settings(
    **{**SEM_IA, 'GEMINI_API_KEY': 'chave-gemini'}, GEMINI_MODEL='modelo-de-teste', IA_LIMITE_POR_HORA=30
)


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

    @override_settings(**SEM_IA)
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

    @override_settings(**SEM_IA)
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

    @override_settings(**SEM_IA, DEBUG=True)
    def test_botao_some_sem_chave(self):
        self.client.force_login(self.marcenaria.usuario)
        resp = self.client.get(reverse('material_novo'))
        self.assertNotContains(resp, 'Preencher com IA')
        self.assertContains(resp, 'GEMINI_API_KEY')  # dica só em modo de desenvolvimento


def resposta_gemini(texto, **extra):
    return {'candidates': [{'content': {'parts': [{'text': texto}]}, **extra}]}


class EscolhaDoProvedorTests(TestCase):
    def test_automatico_prefere_gemini_por_ser_gratuito(self):
        with override_settings(**{**SEM_IA, 'GEMINI_API_KEY': 'g', 'ANTHROPIC_API_KEY': 'a'}):
            self.assertEqual(servico.provedor(), 'gemini')

    def test_so_com_chave_do_claude_usa_claude(self):
        with override_settings(**{**SEM_IA, 'ANTHROPIC_API_KEY': 'a'}):
            self.assertEqual(servico.provedor(), 'anthropic')

    def test_ia_provedor_forca_a_escolha(self):
        with override_settings(GEMINI_API_KEY='g', ANTHROPIC_API_KEY='a', IA_PROVEDOR='anthropic'):
            self.assertEqual(servico.provedor(), 'anthropic')

    def test_provedor_forcado_sem_a_chave_dele_desliga_a_ia(self):
        with override_settings(GEMINI_API_KEY='', ANTHROPIC_API_KEY='a', IA_PROVEDOR='gemini'):
            self.assertIsNone(servico.provedor())
            self.assertFalse(servico.disponivel())

    def test_sem_chave_nenhuma(self):
        with override_settings(**SEM_IA):
            self.assertIsNone(servico.provedor())


@COM_GEMINI
class GeminiTests(TestCase):
    def test_extrair_anuncio_pede_json_e_valida_a_resposta(self):
        with patch.object(servico, '_post_gemini', return_value=resposta_gemini(
            '```json\n{"intencao": "oferta", "categoria": "madeira", "titulo": "Apara de MDF", '
            '"quantidade": 300, "unidade": "kg", "invadido": "x"}\n```'
        )) as post:
            campos = servico.extrair_anuncio('tenho 300 kg de MDF')
        corpo = post.call_args.args[0]
        self.assertEqual(corpo['generationConfig']['responseMimeType'], 'application/json')
        self.assertIn('"categoria"', corpo['systemInstruction']['parts'][0]['text'])
        self.assertIn('<descricao_da_pessoa>', corpo['contents'][0]['parts'][0]['text'])
        self.assertEqual(campos['quantidade'], '300.00')
        self.assertNotIn('invadido', campos)

    def test_json_invalido_vira_erro(self):
        with patch.object(servico, '_post_gemini', return_value=resposta_gemini('isto não é json')):
            with self.assertRaisesMessage(servico.IAErro, 'formato inesperado'):
                servico.extrair_anuncio('tenho 300 kg de MDF')

    def test_partes_de_raciocinio_nao_entram_na_resposta(self):
        dados = {'candidates': [{'content': {'parts': [
            {'text': 'pensando...', 'thought': True}, {'text': 'Olá! Podemos fechar?'},
        ]}}]}
        self.assertEqual(servico._texto_da_resposta_gemini(dados), 'Olá! Podemos fechar?')

    def test_resposta_cortada_ou_bloqueada(self):
        with self.assertRaisesMessage(servico.IAErro, 'cortada'):
            servico._texto_da_resposta_gemini(
                {'candidates': [{'content': {'parts': []}, 'finishReason': 'MAX_TOKENS'}]}
            )
        with self.assertRaisesMessage(servico.IAErro, 'recusou'):
            servico._texto_da_resposta_gemini({'promptFeedback': {'blockReason': 'SAFETY'}})
        with self.assertRaises(servico.IAErro):
            servico._texto_da_resposta_gemini({})

    def test_sugerir_mensagem_pelo_gemini(self):
        marcenaria = criar_empresa('marcenaria')
        briquete = criar_empresa('briquete', cidade='Olinda')
        oferta = criar_material(marcenaria)
        self.client.force_login(briquete.usuario)
        self.client.post(reverse('negociacao_nova', args=[oferta.pk]), {**TERMOS, 'mensagem': 'Olá!'})
        neg = Negociacao.objects.get()
        with patch.object(servico, '_post_gemini', return_value=resposta_gemini('"Podemos fechar por R$ 0,42/kg?"')) as post:
            texto = servico.sugerir_mensagem(neg, briquete, 'pedir desconto')
        self.assertEqual(texto, 'Podemos fechar por R$ 0,42/kg?')
        enviado = post.call_args.args[0]['contents'][0]['parts'][0]['text']
        self.assertIn('pedir desconto', enviado)
        self.assertNotIn('responseMimeType', post.call_args.args[0]['generationConfig'])

    def test_requisicao_http_usa_chave_no_cabecalho_e_modelo_configurado(self):
        class Resposta:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps(resposta_gemini('ok')).encode()

        with patch('ia.servico.urllib.request.urlopen', return_value=Resposta()) as abrir:
            dados = servico._post_gemini({'contents': []})
        pedido = abrir.call_args.args[0]
        self.assertIn('modelo-de-teste:generateContent', pedido.full_url)
        self.assertNotIn('chave-gemini', pedido.full_url)          # a chave nunca vai na URL
        self.assertEqual(pedido.get_header('X-goog-api-key'), 'chave-gemini')
        self.assertEqual(dados['candidates'][0]['content']['parts'][0]['text'], 'ok')

    def test_erros_http_viram_mensagens_amigaveis(self):
        import io
        import urllib.error

        casos = {429: 'limite gratuito', 404: 'GEMINI_MODEL', 400: 'GEMINI_API_KEY', 403: 'GEMINI_API_KEY', 500: 'tente de novo'}
        for codigo, trecho in casos.items():
            erro = urllib.error.HTTPError('http://x', codigo, 'x', {}, io.BytesIO(b'{}'))
            with patch('ia.servico.urllib.request.urlopen', side_effect=erro):
                with self.assertRaises(servico.IAErro) as contexto:
                    servico._post_gemini({})
            self.assertIn(trecho.lower(), str(contexto.exception).lower(), codigo)

    def test_falha_de_rede_vira_erro_amigavel(self):
        import urllib.error

        with patch('ia.servico.urllib.request.urlopen', side_effect=urllib.error.URLError('sem rede')):
            with self.assertRaisesMessage(servico.IAErro, 'Não consegui falar'):
                servico._post_gemini({})

    def test_view_funciona_com_gemini_ligado(self):
        marcenaria = criar_empresa('marcenaria')
        self.client.force_login(marcenaria.usuario)
        with patch.object(servico, '_post_gemini', return_value=resposta_gemini(
            '{"categoria": "madeira", "titulo": "Apara de MDF"}'
        )):
            resp = self.client.post(
                reverse('ia_material'), json.dumps({'texto': 'tenho MDF toda semana'}), content_type='application/json'
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['campos']['categoria'], 'madeira')
