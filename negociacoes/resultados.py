"""Cálculos do painel de resultados (Etapa 5).

Tudo aqui parte de UMA fonte: as negociações CONCLUÍDAS da empresa. Nada é guardado em tabela
nova; o painel é calculado na hora a partir do que já existe, então nunca fica desatualizado.

Duas regras de honestidade que valem para todos os números:
- só kg e toneladas viram "massa" (m³ e unidades não têm conversão confiável e ficam à parte);
- a "economia" só aparece se a empresa informar quanto pagava para descartar uma tonelada.
  Sem esse dado, qualquer valor seria chute.
"""
import csv
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from materiais.models import Material

from .models import Negociacao

# chave na URL -> (texto exibido, quantos dias olhar para trás; None = tudo)
PERIODOS = {
    '30': ('Últimos 30 dias', 30),
    '90': ('Últimos 90 dias', 90),
    '365': ('Últimos 12 meses', 365),
    'tudo': ('Todo o período', None),
}
PERIODO_PADRAO = '90'

CATEGORIAS = dict(Material.CATEGORIAS)
UNIDADES = dict(Material.UNIDADES)
MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
MAX_MESES_NO_GRAFICO = 12
LIMITE_CUSTO_POR_T = Decimal('1000000')


# ---------------------------------------------------------------------------
# Formatação no padrão brasileiro (1.234,56)
# ---------------------------------------------------------------------------

def formatar_numero(valor, casas=2):
    texto = format(Decimal(valor), f',.{casas}f')
    return texto.replace(',', '#').replace('.', ',').replace('#', '.')


def _sem_casas_se_inteiro(valor):
    valor = Decimal(valor)
    return formatar_numero(valor, 0 if valor == valor.to_integral_value() else 2)


def formatar_reais(valor):
    return f'R$ {formatar_numero(valor)}'


def formatar_massa(kg):
    kg = Decimal(kg)
    if kg >= 1000:
        return f'{formatar_numero(kg / 1000)} t'
    return f'{_sem_casas_se_inteiro(kg)} kg'


def massa_em_kg(quantidade, unidade):
    """kg e t viram quilos; m³ e unidades devolvem None (não dá para somar com massa)."""
    if unidade == 'kg':
        return Decimal(quantidade)
    if unidade == 't':
        return Decimal(quantidade) * 1000
    return None


def ler_valor(texto):
    """Lê um valor digitado em reais ('180,50', '1.250,5', 'R$ 90'). Devolve None se inválido."""
    limpo = str(texto or '').replace('R$', '').replace(' ', '').strip()
    if not limpo:
        return None
    if ',' in limpo:
        limpo = limpo.replace('.', '').replace(',', '.')
    try:
        valor = Decimal(limpo)
    except InvalidOperation:
        return None
    if not valor.is_finite() or valor <= 0 or valor > LIMITE_CUSTO_POR_T:
        return None
    return valor.quantize(Decimal('0.01'))


# ---------------------------------------------------------------------------
# Consulta e cálculo
# ---------------------------------------------------------------------------

def dias_do_periodo(chave):
    return PERIODOS.get(chave, PERIODOS[PERIODO_PADRAO])[1]


def concluidas(empresa, chave_periodo):
    qs = (
        Negociacao.objects.da_empresa(empresa)
        .filter(status=Negociacao.CONCLUIDA)
        .select_related('material__empresa', 'proponente', 'recibo')
        .order_by('-concluida_em', '-pk')
    )
    dias = dias_do_periodo(chave_periodo)
    if dias:
        qs = qs.filter(concluida_em__gte=timezone.now() - timedelta(days=dias))
    return list(qs)


def _largura(valor, maximo):
    """Largura da barra em % (as barras menores continuam visíveis)."""
    if not maximo or not valor:
        return 0
    return max(4, int(round(100 * valor / maximo)))


def _quando(neg):
    return timezone.localtime(neg.concluida_em or neg.atualizada_em)


def calcular(empresa, negociacoes, custo_por_t=None):
    parceiras = set()
    massa = {'fornecedora': Decimal('0'), 'receptora': Decimal('0')}
    outras = defaultdict(Decimal)
    receita = gasto = Decimal('0.00')
    doacoes = {'fornecedora': 0, 'receptora': 0}
    por_categoria = defaultdict(lambda: {'negociacoes': 0, 'massa': Decimal('0')})
    por_mes = defaultdict(lambda: {'negociacoes': 0, 'massa': Decimal('0')})

    for neg in negociacoes:
        papel = neg.papel_de(empresa)
        parceiras.add(neg.outra_parte(empresa).pk)
        kg = massa_em_kg(neg.quantidade, neg.material.unidade)
        if kg is None:
            outras[UNIDADES.get(neg.material.unidade, neg.material.unidade)] += neg.quantidade
        else:
            massa[papel] += kg

        if papel == 'fornecedora':
            receita += neg.total
        else:
            gasto += neg.total
        if neg.modalidade == 'doacao':
            doacoes[papel] += 1

        categoria = por_categoria[neg.material.categoria]
        categoria['negociacoes'] += 1
        mes = por_mes[(_quando(neg).year, _quando(neg).month)]
        mes['negociacoes'] += 1
        if kg is not None:
            categoria['massa'] += kg
            mes['massa'] += kg

    maximo = max((c['negociacoes'] for c in por_categoria.values()), default=0)
    categorias = [
        {
            'nome': CATEGORIAS.get(chave, chave),
            'negociacoes': d['negociacoes'],
            'massa': formatar_massa(d['massa']) if d['massa'] else '',
            'largura': _largura(d['negociacoes'], maximo),
        }
        for chave, d in sorted(
            por_categoria.items(), key=lambda item: (-item[1]['negociacoes'], -item[1]['massa'])
        )
    ]

    meses = []
    if por_mes:
        (ano, mes) = min(por_mes)
        fim = _quando_atual()
        sequencia = []
        while (ano, mes) <= (fim.year, fim.month):
            sequencia.append((ano, mes))
            ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
        sequencia = sequencia[-MAX_MESES_NO_GRAFICO:]
        maximo = max((por_mes[k]['negociacoes'] for k in sequencia if k in por_mes), default=0)
        for (ano, mes) in sequencia:
            dados = por_mes.get((ano, mes), {'negociacoes': 0, 'massa': Decimal('0')})
            meses.append({
                'rotulo': f'{MESES[mes - 1]}/{str(ano)[2:]}',
                'negociacoes': dados['negociacoes'],
                'massa': formatar_massa(dados['massa']) if dados['massa'] else '',
                'largura': _largura(dados['negociacoes'], maximo),
            })

    economia = None
    if custo_por_t and massa['fornecedora'] > 0:
        evitado = (massa['fornecedora'] / 1000 * custo_por_t).quantize(Decimal('0.01'))
        economia = {
            'custo': formatar_reais(custo_por_t),
            'massa': formatar_massa(massa['fornecedora']),
            'evitado': formatar_reais(evitado),
            'receita': formatar_reais(receita),
            'total': formatar_reais(evitado + receita),
        }

    return {
        'total': len(negociacoes),
        'parceiras': len(parceiras),
        'desviado': formatar_massa(massa['fornecedora']),
        'recebido': formatar_massa(massa['receptora']),
        'receita': formatar_reais(receita),
        'gasto': formatar_reais(gasto),
        'doacoes_dadas': doacoes['fornecedora'],
        'doacoes_recebidas': doacoes['receptora'],
        'outras_unidades': ', '.join(f'{_sem_casas_se_inteiro(q)} {u}' for u, q in outras.items()),
        'categorias': categorias,
        'meses': meses,
        'economia': economia,
    }


def _quando_atual():
    return timezone.localtime(timezone.now())


# ---------------------------------------------------------------------------
# Exportação em CSV (abre direto no Excel em português)
# ---------------------------------------------------------------------------

CABECALHO_CSV = [
    'Recibo', 'Data', 'Material', 'Categoria', 'Meu papel', 'Outra empresa', 'Local',
    'Quantidade', 'Unidade', 'Modalidade', 'Preço unitário (R$)', 'Total (R$)',
]


def celula_segura(valor):
    """Impede 'injeção de fórmula': nome de empresa como =HYPERLINK(...) viraria fórmula no Excel."""
    texto = str(valor)
    return "'" + texto if texto[:1] in ('=', '+', '-', '@', '\t', '\r') else texto


def escrever_csv(destino, empresa, negociacoes):
    escritor = csv.writer(destino, delimiter=';')
    escritor.writerow(CABECALHO_CSV)
    for neg in negociacoes:
        outra = neg.outra_parte(empresa)
        escritor.writerow([
            celula_segura(valor) for valor in (
                neg.recibo.codigo,
                _quando(neg).strftime('%d/%m/%Y'),
                neg.material.titulo,
                CATEGORIAS.get(neg.material.categoria, neg.material.categoria),
                'Fornecedora' if neg.papel_de(empresa) == 'fornecedora' else 'Receptora',
                outra.nome,
                f'{outra.cidade}/{outra.estado}',
                formatar_numero(neg.quantidade),
                UNIDADES.get(neg.material.unidade, neg.material.unidade),
                neg.get_modalidade_display(),
                formatar_numero(neg.preco) if neg.modalidade == 'venda' and neg.preco else '',
                formatar_numero(neg.total),
            )
        ])
