from decimal import Decimal

from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from contas.models import Empresa
from materiais.models import Material


class AcaoInvalida(Exception):
    """Ação que não pode ser feita no estado atual da negociação."""


class NegociacaoQuerySet(models.QuerySet):
    def da_empresa(self, empresa):
        return self.filter(Q(proponente=empresa) | Q(material__empresa=empresa))

    def pendentes_de(self, empresa):
        """Negociações que dependem de uma ação da empresa (responder ou confirmar entrega)."""
        sou_fornecedora = Q(material__intencao='oferta', material__empresa=empresa) | Q(
            material__intencao='procura', proponente=empresa
        )
        sou_receptora = Q(material__intencao='procura', material__empresa=empresa) | Q(
            material__intencao='oferta', proponente=empresa
        )
        responder = Q(status=Negociacao.ABERTA) & ~Q(ultima_alteracao_por=empresa)
        confirmar = Q(status=Negociacao.ACEITA) & (
            (sou_fornecedora & Q(confirmou_fornecedora=False))
            | (sou_receptora & Q(confirmou_receptora=False))
        )
        return self.da_empresa(empresa).filter(responder | confirmar)


class Negociacao(models.Model):
    """Proposta de uma empresa sobre o anúncio de outra, com os termos em discussão.

    Papéis: a empresa FORNECEDORA é quem entrega o material e a RECEPTORA é quem o recebe.
    Em um anúncio de oferta, o dono do anúncio é a fornecedora; em um de procura, é a receptora.
    """

    ABERTA, ACEITA, RECUSADA, CANCELADA, CONCLUIDA = (
        'aberta', 'aceita', 'recusada', 'cancelada', 'concluida'
    )
    STATUS = [
        (ABERTA, 'Em negociação'),
        (ACEITA, 'Aceita, aguardando entrega'),
        (RECUSADA, 'Recusada'),
        (CANCELADA, 'Cancelada'),
        (CONCLUIDA, 'Concluída'),
    ]
    MODALIDADES = [('venda', 'Venda'), ('doacao', 'Doação')]
    RETIRADAS = [
        ('receptora', 'Quem recebe retira o material'),
        ('fornecedora', 'Quem fornece entrega o material'),
    ]

    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='negociacoes')
    proponente = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='propostas_feitas')
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    preco = models.DecimalField(
        'preço por unidade (R$)', max_digits=10, decimal_places=2, null=True, blank=True
    )
    modalidade = models.CharField(max_length=10, choices=MODALIDADES, default='venda')
    retirada = models.CharField('logística', max_length=12, choices=RETIRADAS, default='receptora')
    status = models.CharField(max_length=10, choices=STATUS, default=ABERTA)
    ultima_alteracao_por = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name='+',
        help_text='Quem mexeu nos termos por último. A outra parte é quem pode aceitar.',
    )
    confirmou_fornecedora = models.BooleanField(default=False)
    confirmou_receptora = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    aceita_em = models.DateTimeField(null=True, blank=True)
    concluida_em = models.DateTimeField(null=True, blank=True)

    objects = NegociacaoQuerySet.as_manager()

    class Meta:
        ordering = ['-atualizada_em']
        verbose_name = 'negociação'
        verbose_name_plural = 'negociações'

    def __str__(self):
        return f'{self.material.titulo}: {self.proponente}'

    # ---------- papéis ----------
    @property
    def destinataria(self):
        """Dona do anúncio que recebeu a proposta."""
        return self.material.empresa

    @property
    def fornecedora(self):
        return self.destinataria if self.material.intencao == 'oferta' else self.proponente

    @property
    def receptora(self):
        return self.proponente if self.material.intencao == 'oferta' else self.destinataria

    def participa(self, empresa):
        return empresa.pk in (self.proponente_id, self.destinataria.pk)

    def outra_parte(self, empresa):
        return self.destinataria if empresa.pk == self.proponente_id else self.proponente

    def papel_de(self, empresa):
        return 'fornecedora' if empresa.pk == self.fornecedora.pk else 'receptora'

    # ---------- valores ----------
    @property
    def total(self):
        if self.modalidade == 'venda' and self.preco:
            return (self.quantidade * self.preco).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def ativa(self):
        return self.status in (self.ABERTA, self.ACEITA)

    def resumo(self):
        """Termos em uma frase, para o histórico. Ex.: 300 kg, R$ 0.40 por kg, venda, quem recebe retira."""
        unidade = self.material.get_unidade_display()
        partes = [f'{format(self.quantidade.normalize(), "f")} {unidade}']
        if self.modalidade == 'venda' and self.preco:
            partes.append(f'R$ {self.preco:.2f} por {unidade}'.replace('.', ','))
        partes.append(self.get_modalidade_display().lower())
        partes.append(self.get_retirada_display().lower())
        return ', '.join(partes)

    def vez_de(self, empresa):
        """True se a próxima ação depende desta empresa."""
        if self.status == self.ABERTA:
            return self.ultima_alteracao_por_id != empresa.pk
        if self.status == self.ACEITA:
            if self.papel_de(empresa) == 'fornecedora':
                return not self.confirmou_fornecedora
            return not self.confirmou_receptora
        return False

    def confirmou(self, empresa):
        if self.papel_de(empresa) == 'fornecedora':
            return self.confirmou_fornecedora
        return self.confirmou_receptora

    # ---------- histórico ----------
    def registrar(self, texto, autor=None):
        """Grava uma mensagem no histórico (autor None = aviso do sistema)."""
        return self.mensagens.create(autor=autor, texto=texto, sistema=autor is None)

    # ---------- ações (as regras de negócio ficam aqui, não nas views) ----------
    def _exigir(self, condicao, mensagem):
        if not condicao:
            raise AcaoInvalida(mensagem)

    def alterar_termos(self, empresa, quantidade, preco, modalidade, retirada, resumo):
        self._exigir(self.status == self.ABERTA, 'Só dá para alterar os termos enquanto a negociação está aberta.')
        self._exigir(self.participa(empresa), 'Você não participa desta negociação.')
        self.quantidade, self.preco = quantidade, preco
        self.modalidade, self.retirada = modalidade, retirada
        self.ultima_alteracao_por = empresa
        self.save()
        self.registrar(f'{empresa.nome} alterou os termos: {resumo}.')

    def aceitar(self, empresa):
        self._exigir(self.status == self.ABERTA, 'Esta negociação não está aberta.')
        self._exigir(self.participa(empresa), 'Você não participa desta negociação.')
        self._exigir(
            self.ultima_alteracao_por_id != empresa.pk,
            'Você fez a última alteração. Quem aceita é a outra empresa.',
        )
        self.status = self.ACEITA
        self.aceita_em = timezone.now()
        self.save()
        self.registrar(f'{empresa.nome} aceitou os termos. Combinem a entrega e confirmem quando ela acontecer.')

    def encerrar(self, empresa):
        """Destinatária recusa; proponente cancela."""
        self._exigir(self.status == self.ABERTA, 'Esta negociação não está aberta.')
        self._exigir(self.participa(empresa), 'Você não participa desta negociação.')
        if empresa.pk == self.proponente_id:
            self.status = self.CANCELADA
            verbo = 'cancelou a proposta'
        else:
            self.status = self.RECUSADA
            verbo = 'recusou a proposta'
        self.save()
        self.registrar(f'{empresa.nome} {verbo}.')

    @transaction.atomic
    def confirmar_entrega(self, empresa):
        """Cada parte confirma; quando as duas confirmam, a negociação conclui e gera o recibo."""
        self._exigir(self.status == self.ACEITA, 'A negociação precisa estar aceita para confirmar a entrega.')
        self._exigir(self.participa(empresa), 'Você não participa desta negociação.')
        if self.papel_de(empresa) == 'fornecedora':
            self.confirmou_fornecedora = True
            self.registrar(f'{empresa.nome} confirmou que entregou o material.')
        else:
            self.confirmou_receptora = True
            self.registrar(f'{empresa.nome} confirmou que recebeu o material.')

        if self.confirmou_fornecedora and self.confirmou_receptora:
            self.status = self.CONCLUIDA
            self.concluida_em = timezone.now()
            self.save()
            Recibo.emitir(self)
            self._baixar_estoque()
            self.registrar('Entrega confirmada pelas duas empresas. Recibo emitido.')
        else:
            self.save()

    def _baixar_estoque(self):
        """Anúncio de entrega única sai da busca quando todo o volume foi negociado."""
        material = self.material
        if material.frequencia != 'unica':
            return
        material.quantidade = max(material.quantidade - self.quantidade, Decimal('0'))
        if material.quantidade == 0:
            material.ativo = False
        material.save()


class Mensagem(models.Model):
    negociacao = models.ForeignKey(Negociacao, on_delete=models.CASCADE, related_name='mensagens')
    autor = models.ForeignKey(Empresa, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    texto = models.TextField(max_length=1000)
    sistema = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criada_em', 'pk']

    def __str__(self):
        return f'{self.autor or "Sistema"}: {self.texto[:40]}'


class Recibo(models.Model):
    """Registro da transação concluída. Guarda uma cópia dos dados do momento da entrega."""

    negociacao = models.OneToOneField(Negociacao, on_delete=models.PROTECT, related_name='recibo')
    emitido_em = models.DateTimeField(auto_now_add=True)
    fornecedora_nome = models.CharField(max_length=120)
    fornecedora_local = models.CharField(max_length=100)
    receptora_nome = models.CharField(max_length=120)
    receptora_local = models.CharField(max_length=100)
    material_titulo = models.CharField(max_length=100)
    categoria = models.CharField(max_length=30)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    unidade = models.CharField(max_length=10)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    modalidade = models.CharField(max_length=30)
    logistica = models.CharField(max_length=60)

    class Meta:
        ordering = ['-emitido_em']

    @property
    def codigo(self):
        return f'EI-{self.emitido_em.year}-{self.pk:06d}'

    def __str__(self):
        return self.codigo

    @classmethod
    def emitir(cls, neg):
        f, r, m = neg.fornecedora, neg.receptora, neg.material
        return cls.objects.create(
            negociacao=neg,
            fornecedora_nome=f.nome,
            fornecedora_local=f'{f.cidade}/{f.estado}',
            receptora_nome=r.nome,
            receptora_local=f'{r.cidade}/{r.estado}',
            material_titulo=m.titulo,
            categoria=m.get_categoria_display(),
            quantidade=neg.quantidade,
            unidade=m.get_unidade_display(),
            preco_unitario=neg.preco if neg.modalidade == 'venda' else None,
            valor_total=neg.total,
            modalidade=neg.get_modalidade_display(),
            logistica=neg.get_retirada_display(),
        )
