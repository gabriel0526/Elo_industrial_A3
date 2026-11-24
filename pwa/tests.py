import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from negociacoes.tests import criar_empresa


class ManifestoTests(TestCase):
    def setUp(self):
        resp = self.client.get('/manifest.webmanifest')
        self.resp = resp
        self.dados = json.loads(resp.content)

    def test_tipo_correto_e_campos_obrigatorios(self):
        self.assertEqual(self.resp.status_code, 200)
        self.assertEqual(self.resp['Content-Type'], 'application/manifest+json')
        self.assertEqual(self.dados['display'], 'standalone')
        self.assertEqual(self.dados['start_url'], '/')
        self.assertEqual(self.dados['scope'], '/')
        self.assertTrue(self.dados['name'] and self.dados['short_name'])

    def test_tem_icones_de_192_e_512_e_um_maskable(self):
        tamanhos = {i['sizes'] for i in self.dados['icons']}
        self.assertTrue({'192x192', '512x512'} <= tamanhos)
        self.assertTrue(any(i['purpose'] == 'maskable' for i in self.dados['icons']))

    def test_icones_existem_e_tem_o_tamanho_declarado(self):
        for icone in self.dados['icons']:
            caminho = Path(settings.BASE_DIR) / icone['src'].lstrip('/')
            self.assertTrue(caminho.exists(), icone['src'])
            largura, altura = Image.open(caminho).size
            self.assertEqual(f'{largura}x{altura}', icone['sizes'])

    def test_atalhos_apontam_para_paginas_do_site(self):
        urls = [a['url'] for a in self.dados['shortcuts']]
        self.assertEqual(urls, [reverse('buscar'), reverse('negociacoes_lista'), reverse('resultados')])


class ServiceWorkerTests(TestCase):
    def setUp(self):
        self.resp = self.client.get('/sw.js')
        self.js = self.resp.content.decode()

    def test_cabecalhos(self):
        self.assertEqual(self.resp.status_code, 200)
        self.assertTrue(self.resp['Content-Type'].startswith('application/javascript'))
        self.assertEqual(self.resp['Cache-Control'], 'no-cache')
        self.assertEqual(self.resp['Service-Worker-Allowed'], '/')

    def test_usa_a_versao_das_configuracoes_e_guarda_a_pagina_offline(self):
        self.assertIn(settings.PWA_VERSION, self.js)
        self.assertIn("PAGINA_OFFLINE = '/offline/'", self.js)
        self.assertIn('/static/css/estilo.css', self.js)

    def test_nao_mexe_em_formularios_nem_guarda_paginas_do_usuario(self):
        self.assertIn("requisicao.method !== 'GET'", self.js)
        # só os arquivos estáticos entram no cache; páginas só têm o fallback offline
        self.assertEqual(self.js.count('cache.put('), 1)

    def test_somente_get(self):
        self.assertEqual(self.client.post('/sw.js').status_code, 405)


class OfflineETelasTests(TestCase):
    def test_pagina_offline_abre_sem_login(self):
        resp = self.client.get(reverse('offline'))
        self.assertContains(resp, 'sem conexão')
        self.assertContains(resp, 'Tentar de novo')

    def test_paginas_trazem_o_manifesto_e_o_registro_do_app(self):
        resp = self.client.get(reverse('home'))
        self.assertContains(resp, 'rel="manifest"')
        self.assertContains(resp, 'apple-touch-icon')
        self.assertContains(resp, 'js/pwa.js')
        self.assertContains(resp, 'viewport-fit=cover')

    def test_barra_de_abas_so_para_quem_esta_logado(self):
        self.assertNotContains(self.client.get(reverse('home')), 'abas-app')
        empresa = criar_empresa('marcenaria')
        self.client.force_login(empresa.usuario)
        resp = self.client.get(reverse('resultados'))
        self.assertContains(resp, 'class="abas-app"')
        for nome in ('Buscar', 'Negociações', 'Resultados', 'Painel'):
            self.assertContains(resp, f'<span>{nome}')

    def test_aba_da_pagina_atual_fica_marcada(self):
        empresa = criar_empresa('marcenaria')
        self.client.force_login(empresa.usuario)
        html = self.client.get(reverse('resultados')).content.decode()
        trecho = html.split('class="abas-app"')[1]
        self.assertEqual(trecho.count('aria-current="page"'), 1)
        self.assertIn(reverse('resultados'), trecho.split('aria-current="page"')[0].rsplit('<a ', 1)[1])
