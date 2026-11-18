"""Distância entre empresas.

Para o MVP usamos uma tabelinha com as coordenadas das capitais e de algumas cidades
de Pernambuco. Cidade que não está na tabela fica sem coordenada e o sistema usa
"mesma cidade / mesmo estado" como aproximação. Na etapa de produção dá para trocar
essa tabela por uma API de geocodificação sem mexer no resto do código.
"""
import unicodedata
from math import asin, cos, radians, sin, sqrt


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return texto.strip().lower()


# (cidade, UF): (latitude, longitude)
_CIDADES = {
    # Região metropolitana do Recife e principais polos de Pernambuco
    ('Recife', 'PE'): (-8.0476, -34.8770),
    ('Jaboatão dos Guararapes', 'PE'): (-8.1130, -35.0148),
    ('Olinda', 'PE'): (-8.0089, -34.8553),
    ('Paulista', 'PE'): (-7.9408, -34.8731),
    ('Camaragibe', 'PE'): (-8.0206, -34.9780),
    ('São Lourenço da Mata', 'PE'): (-8.0021, -35.0170),
    ('Igarassu', 'PE'): (-7.8342, -34.9069),
    ('Cabo de Santo Agostinho', 'PE'): (-8.2864, -35.0348),
    ('Ipojuca', 'PE'): (-8.3996, -35.0626),
    ('Goiana', 'PE'): (-7.5603, -35.0020),
    ('Vitória de Santo Antão', 'PE'): (-8.1177, -35.2914),
    ('Gravatá', 'PE'): (-8.2012, -35.5647),
    ('Caruaru', 'PE'): (-8.2760, -35.9819),
    ('Garanhuns', 'PE'): (-8.8908, -36.4966),
    ('Petrolina', 'PE'): (-9.3891, -40.5027),
    # Capitais
    ('Rio Branco', 'AC'): (-9.9747, -67.8243),
    ('Maceió', 'AL'): (-9.6658, -35.7353),
    ('Macapá', 'AP'): (0.0349, -51.0694),
    ('Manaus', 'AM'): (-3.1190, -60.0217),
    ('Salvador', 'BA'): (-12.9714, -38.5014),
    ('Fortaleza', 'CE'): (-3.7319, -38.5267),
    ('Brasília', 'DF'): (-15.7939, -47.8828),
    ('Vitória', 'ES'): (-20.3155, -40.3128),
    ('Goiânia', 'GO'): (-16.6869, -49.2648),
    ('São Luís', 'MA'): (-2.5307, -44.3068),
    ('Cuiabá', 'MT'): (-15.6014, -56.0979),
    ('Campo Grande', 'MS'): (-20.4697, -54.6201),
    ('Belo Horizonte', 'MG'): (-19.9167, -43.9345),
    ('Belém', 'PA'): (-1.4558, -48.4902),
    ('João Pessoa', 'PB'): (-7.1195, -34.8450),
    ('Curitiba', 'PR'): (-25.4284, -49.2733),
    ('Teresina', 'PI'): (-5.0892, -42.8019),
    ('Rio de Janeiro', 'RJ'): (-22.9068, -43.1729),
    ('Natal', 'RN'): (-5.7945, -35.2110),
    ('Porto Alegre', 'RS'): (-30.0346, -51.2177),
    ('Porto Velho', 'RO'): (-8.7612, -63.9039),
    ('Boa Vista', 'RR'): (2.8235, -60.6758),
    ('Florianópolis', 'SC'): (-27.5949, -48.5482),
    ('São Paulo', 'SP'): (-23.5505, -46.6333),
    ('Aracaju', 'SE'): (-10.9472, -37.0731),
    ('Palmas', 'TO'): (-10.2491, -48.3243),
}

COORDENADAS = {(_normalizar(c), uf): xy for (c, uf), xy in _CIDADES.items()}


def coordenadas(cidade, estado):
    """Retorna (latitude, longitude) ou None se a cidade não estiver na tabela."""
    return COORDENADAS.get((_normalizar(cidade), (estado or '').upper()))


def distancia_km(a, b):
    """Distância em linha reta (fórmula de Haversine) entre dois pontos (lat, lon)."""
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))
