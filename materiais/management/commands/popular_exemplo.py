"""Cria empresas e anúncios de exemplo para testar a busca e o match.

Uso:  python manage.py popular_exemplo
Todas as empresas de exemplo usam a senha:  exemplo12345
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from contas.models import Empresa
from materiais.models import Material
from negociacoes.models import Negociacao

EMPRESAS = [
    ('Marcenaria Boa Madeira', 'gerador', 'Recife', 'PE'),
    ('Briquetes Nordeste', 'comprador', 'Olinda', 'PE'),
    ('Plásticos Suape', 'gerador', 'Ipojuca', 'PE'),
    ('Reciclagem Caruaru', 'comprador', 'Caruaru', 'PE'),
    ('Têxtil Agreste', 'gerador', 'Caruaru', 'PE'),
    ('Metalúrgica Bahia', 'ambos', 'Salvador', 'BA'),
]

# (empresa, intenção, categoria, título, quantidade, unidade, frequência, modalidade, preço)
ANUNCIOS = [
    (0, 'oferta', 'madeira', 'Apara de madeira (MDF e pinus)', 300, 'kg', 'semanal', 'venda', '0.40'),
    (1, 'procura', 'madeira', 'Procuro apara de madeira para briquete', 250, 'kg', 'semanal', 'negociavel', None),
    (2, 'oferta', 'plastico', 'Aparas de PET limpo', 2, 't', 'mensal', 'venda', '900.00'),
    (3, 'procura', 'plastico', 'Compro PET para reciclagem', 3, 't', 'mensal', 'venda', None),
    (4, 'oferta', 'tecido', 'Retalhos de malha', 150, 'kg', 'semanal', 'doacao', None),
    (5, 'oferta', 'metal', 'Cavaco de aço', 5, 't', 'unica', 'venda', '1200.00'),
    (5, 'procura', 'madeira', 'Preciso de paletes de madeira', 80, 'un', 'mensal', 'negociavel', None),
]


class Command(BaseCommand):
    help = 'Cria dados de exemplo (empresas e anúncios).'

    def handle(self, *args, **opcoes):
        User = get_user_model()
        empresas = []
        for nome, tipo, cidade, estado in EMPRESAS:
            email = nome.lower().replace(' ', '').replace('á', 'a').replace('é', 'e') + '@exemplo.com'
            usuario, criado = User.objects.get_or_create(username=email, defaults={'email': email})
            if criado:
                usuario.set_password('exemplo12345')
                usuario.save()
            empresa, _ = Empresa.objects.get_or_create(
                usuario=usuario,
                defaults={'nome': nome, 'tipo': tipo, 'cidade': cidade, 'estado': estado},
            )
            empresas.append(empresa)

        novos = 0
        for i, intencao, cat, titulo, qtd, un, freq, mod, preco in ANUNCIOS:
            _, criado = Material.objects.get_or_create(
                empresa=empresas[i], titulo=titulo,
                defaults=dict(
                    intencao=intencao, categoria=cat, quantidade=Decimal(qtd), unidade=un,
                    frequencia=freq, modalidade=mod, preco=Decimal(preco) if preco else None,
                ),
            )
            novos += criado
        self.criar_negociacoes(empresas)
        self.stdout.write(self.style.SUCCESS(f'Pronto: {len(empresas)} empresas e {novos} anúncios novos.'))

    def criar_negociacoes(self, empresas):
        """Uma negociação aberta (esperando a Marcenaria) e uma concluída, com recibo."""
        marcenaria, briquetes, _, reciclagem, textil, _ = empresas

        apara = Material.objects.get(empresa=marcenaria, titulo__startswith='Apara de madeira')
        if not Negociacao.objects.filter(material=apara).exists():
            neg = Negociacao.objects.create(
                material=apara, proponente=briquetes, ultima_alteracao_por=briquetes,
                quantidade=Decimal('250'), preco=Decimal('0.35'), modalidade='venda', retirada='receptora',
            )
            neg.registrar(f'{briquetes.nome} enviou uma proposta: {neg.resumo()}.')
            neg.registrar('Bom dia! Conseguimos retirar toda quinta-feira de manhã.', autor=briquetes)

        malha = Material.objects.get(empresa=textil, titulo='Retalhos de malha')
        if not Negociacao.objects.filter(material=malha).exists():
            neg = Negociacao.objects.create(
                material=malha, proponente=reciclagem, ultima_alteracao_por=reciclagem,
                quantidade=Decimal('150'), modalidade='doacao', retirada='receptora',
            )
            neg.registrar(f'{reciclagem.nome} enviou uma proposta: {neg.resumo()}.')
            neg.aceitar(textil)
            neg.confirmar_entrega(textil)
            neg.confirmar_entrega(reciclagem)
