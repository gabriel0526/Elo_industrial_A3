"""Faz o site virar um app instalável (PWA): manifesto, service worker e página offline.

Os três endereços precisam ficar na RAIZ do site (/manifest.webmanifest, /sw.js): um service worker
só controla as páginas que estão dentro da pasta onde ele é servido.
"""
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_GET

COR_FUNDO = '#e8ebe9'   # --concreto
COR_TEMA = '#2d5c44'    # --musgo (barra de status do celular)


def _icone(arquivo, tamanho, finalidade='any'):
    return {'src': static(f'icons/{arquivo}'), 'sizes': f'{tamanho}x{tamanho}', 'type': 'image/png', 'purpose': finalidade}


@require_GET
def manifesto(request):
    dados = {
        'id': '/',
        'name': 'Elo Industrial',
        'short_name': 'Elo',
        'description': 'Marketplace de resíduos industriais: o resíduo de uma empresa é a matéria-prima de outra.',
        'lang': 'pt-BR',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'background_color': COR_FUNDO,
        'theme_color': COR_TEMA,
        'icons': [
            _icone('icone-192.png', 192),
            _icone('icone-512.png', 512),
            _icone('icone-maskable-512.png', 512, 'maskable'),
        ],
        'shortcuts': [
            {'name': 'Buscar materiais', 'url': reverse('buscar')},
            {'name': 'Negociações', 'url': reverse('negociacoes_lista')},
            {'name': 'Resultados', 'url': reverse('resultados')},
        ],
    }
    resposta = JsonResponse(dados, content_type='application/manifest+json')
    resposta['Cache-Control'] = 'public, max-age=3600'
    return resposta


@require_GET
def service_worker(request):
    conteudo = render(request, 'pwa/sw.js', {
        'versao': settings.PWA_VERSION,
        'pagina_offline': reverse('offline'),
        'arquivos': [
            static('css/estilo.css'),
            static('js/pwa.js'),
            static('icons/icone-192.png'),
            static('icons/apple-touch-icon.png'),
        ],
    }).content
    resposta = HttpResponse(conteudo, content_type='application/javascript; charset=utf-8')
    # o navegador precisa checar o arquivo a cada visita para perceber quando há versão nova
    resposta['Cache-Control'] = 'no-cache'
    resposta['Service-Worker-Allowed'] = '/'
    return resposta


@require_GET
def offline(request):
    return render(request, 'pwa/offline.html')
