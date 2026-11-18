from django.db import models

from contas.models import Empresa


class Material(models.Model):
    """Um anúncio: a empresa oferece um resíduo ou procura um material."""

    INTENCOES = [
        ('oferta', 'Tenho este material'),
        ('procura', 'Preciso deste material'),
    ]
    CATEGORIAS = [
        ('madeira', 'Madeira'),
        ('plastico', 'Plástico'),
        ('metal', 'Metal'),
        ('tecido', 'Tecido'),
        ('papel', 'Papel e papelão'),
        ('vidro', 'Vidro'),
        ('borracha', 'Borracha'),
        ('outros', 'Outros'),
    ]
    UNIDADES = [
        ('kg', 'kg'),
        ('t', 'ton'),
        ('m3', 'm³'),
        ('un', 'un'),
    ]
    FREQUENCIAS = [
        ('unica', 'Uma vez só'),
        ('semanal', 'Toda semana'),
        ('mensal', 'Todo mês'),
    ]
    MODALIDADES = [
        ('venda', 'Venda'),
        ('doacao', 'Doação'),
        ('negociavel', 'A combinar'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='materiais')
    intencao = models.CharField('você', max_length=8, choices=INTENCOES, default='oferta')
    categoria = models.CharField(max_length=10, choices=CATEGORIAS)
    titulo = models.CharField('título', max_length=100)
    descricao = models.TextField('descrição', blank=True)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    unidade = models.CharField(max_length=3, choices=UNIDADES, default='kg')
    frequencia = models.CharField('frequência', max_length=8, choices=FREQUENCIAS, default='unica')
    modalidade = models.CharField(max_length=10, choices=MODALIDADES, default='negociavel')
    preco = models.DecimalField(
        'preço por unidade (R$)', max_digits=10, decimal_places=2, null=True, blank=True
    )
    foto = models.ImageField(upload_to='materiais/', blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name_plural = 'materiais'

    def __str__(self):
        return f'{self.titulo} ({self.empresa})'
