"""Motor de match (versão por regras).

Dado um anúncio de OFERTA, procura os anúncios de PROCURA compatíveis (e o contrário).
Cada combinação recebe uma pontuação de 0 a 100, somando quatro critérios, e uma lista
de motivos em português para explicar o resultado ao usuário:

    distância    até 40 pontos
    volume       até 30 pontos
    modalidade   até 15 pontos   (venda x doação x a combinar)
    frequência   até 15 pontos

A categoria precisa ser a mesma, senão nem entra na lista. Na etapa de IA, este mesmo
formato de pontuação poderá ser substituído por um modelo que aprende com o histórico.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from .models import Material

PONTUACAO_MINIMA = 40
LIMITE_PADRAO = 5

# conversão para uma unidade base, quando faz sentido comparar (kg e tonelada)
_PARA_KG = {'kg': Decimal(1), 't': Decimal(1000)}


@dataclass
class Combinacao:
    material: Material
    pontuacao: int
    distancia: float | None
    motivos: list = field(default_factory=list)


def _pontos_distancia(a, b):
    """Retorna (pontos, distancia_km, motivo)."""
    km = a.empresa.distancia_ate(b.empresa)
    if km is not None:
        if km <= 25:
            return 40, km, f'a {km:.0f} km de distância'
        if km <= 100:
            return 30, km, f'a {km:.0f} km de distância'
        if km <= 300:
            return 20, km, f'a {km:.0f} km de distância'
        if km <= 800:
            return 10, km, f'a {km:.0f} km de distância'
        return 0, km, f'distante, a {km:.0f} km'
    # sem coordenadas: compara cidade e estado
    ea, eb = a.empresa, b.empresa
    if ea.estado == eb.estado and ea.cidade.strip().lower() == eb.cidade.strip().lower():
        return 40, None, 'na mesma cidade'
    if ea.estado == eb.estado:
        return 20, None, 'no mesmo estado'
    return 0, None, 'em estados diferentes'


def _pontos_volume(a, b):
    ua, ub = a.unidade, b.unidade
    if ua in _PARA_KG and ub in _PARA_KG:
        qa, qb = a.quantidade * _PARA_KG[ua], b.quantidade * _PARA_KG[ub]
    elif ua == ub:
        qa, qb = a.quantidade, b.quantidade
    else:
        return 10, 'unidades diferentes, confirme o volume'
    if qa <= 0 or qb <= 0:
        return 0, ''
    razao = float(min(qa, qb) / max(qa, qb))
    if razao >= 0.8:
        return 30, 'volume muito parecido'
    if razao >= 0.5:
        return 22, 'volume compatível'
    if razao >= 0.25:
        return 14, 'volume um pouco diferente'
    return 6, 'volume bem diferente'


def _pontos_modalidade(a, b):
    ma, mb = a.modalidade, b.modalidade
    if ma == mb:
        return 15, f'ambos em modalidade de {a.get_modalidade_display().lower()}'
    if 'negociavel' in (ma, mb):
        return 12, 'modalidade a combinar'
    return 0, 'modalidades diferentes (venda x doação)'


def _pontos_frequencia(a, b):
    if a.frequencia == b.frequencia:
        return 15, 'mesma frequência'
    return 7, 'frequências diferentes'


def avaliar(base, candidato):
    """Calcula a combinação entre dois anúncios."""
    p_dist, km, m_dist = _pontos_distancia(base, candidato)
    p_vol, m_vol = _pontos_volume(base, candidato)
    p_mod, m_mod = _pontos_modalidade(base, candidato)
    p_freq, m_freq = _pontos_frequencia(base, candidato)
    motivos = [m for m in (m_dist, m_vol, m_mod, m_freq) if m]
    return Combinacao(
        material=candidato,
        pontuacao=p_dist + p_vol + p_mod + p_freq,
        distancia=km,
        motivos=motivos,
    )


def combinacoes_para(material, limite=LIMITE_PADRAO, minimo=PONTUACAO_MINIMA):
    """Anúncios do lado oposto (oferta x procura) que combinam com o material dado."""
    lado_oposto = 'procura' if material.intencao == 'oferta' else 'oferta'
    candidatos = (
        Material.objects.filter(
            ativo=True, intencao=lado_oposto, categoria=material.categoria
        )
        .exclude(empresa=material.empresa)
        .select_related('empresa')
    )
    resultado = [avaliar(material, c) for c in candidatos]
    resultado = [r for r in resultado if r.pontuacao >= minimo]
    resultado.sort(key=lambda r: r.pontuacao, reverse=True)
    return resultado[:limite]
