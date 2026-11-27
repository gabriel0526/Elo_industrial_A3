"""Atualização automática das negociações (Etapa 8).

Como funciona, em uma frase: a página pergunta ao servidor a cada poucos segundos "mudou alguma coisa?";
a resposta é só um código curto (a "versão"). Se o código mudou, a página busca a si mesma de novo e troca
apenas os trechos que mudaram. Quem digita uma mensagem não é interrompido: o campo de texto fica fora
dos trechos trocados.

Escolhi esse caminho (e não WebSocket) porque funciona com o servidor normal do Django, no Codespaces, sem
instalar nada e sem mexer no banco. O custo é um pequeno atraso (alguns segundos) em vez de instantâneo.
"""
import hashlib

from django.db.models import Count, Max

from .models import Negociacao


def _codigo(*partes):
    return hashlib.sha1('|'.join(str(p) for p in partes).encode('utf-8')).hexdigest()[:12]


def versao_da_negociacao(neg):
    """Muda sempre que os termos, a situação, as confirmações ou a conversa mudam."""
    mensagens = neg.mensagens.aggregate(total=Count('pk'), ultima=Max('pk'))
    return _codigo(
        neg.atualizada_em.isoformat(), neg.status, neg.confirmou_fornecedora, neg.confirmou_receptora,
        neg.quantidade, neg.preco, neg.modalidade, neg.retirada, mensagens['total'], mensagens['ultima'],
    )


def versao_das_negociacoes(empresa):
    """Muda quando qualquer negociação da empresa muda, nasce ou passa a esperar uma ação dela."""
    resumo = Negociacao.objects.da_empresa(empresa).aggregate(total=Count('pk'), ultima=Max('atualizada_em'))
    pendentes = Negociacao.objects.pendentes_de(empresa).count()
    return _codigo(resumo['total'], resumo['ultima'], pendentes), pendentes
