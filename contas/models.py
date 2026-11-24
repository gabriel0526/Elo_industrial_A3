from django.conf import settings
from django.db import models

from materiais.geo import coordenadas, distancia_km


class Empresa(models.Model):
    """Perfil da empresa, ligado ao usuário que faz login."""

    TIPOS = [
        ('gerador', 'Gero resíduo e quero destiná-lo'),
        ('comprador', 'Preciso de material como insumo'),
        ('ambos', 'As duas coisas'),
    ]

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='empresa'
    )
    nome = models.CharField('nome da empresa', max_length=120)
    tipo = models.CharField('o que a empresa faz na plataforma', max_length=10, choices=TIPOS)
    cidade = models.CharField(max_length=80)
    estado = models.CharField(max_length=2, help_text='Sigla, por exemplo PE')
    telefone = models.CharField(max_length=20, blank=True)
    latitude = models.FloatField(null=True, blank=True, editable=False)
    longitude = models.FloatField(null=True, blank=True, editable=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']

    def save(self, *args, **kwargs):
        # preenche latitude/longitude pela cidade, para calcular distâncias
        xy = coordenadas(self.cidade, self.estado)
        self.latitude, self.longitude = xy if xy else (None, None)
        super().save(*args, **kwargs)

    @property
    def ponto(self):
        if self.latitude is None or self.longitude is None:
            return None
        return (self.latitude, self.longitude)

    def distancia_ate(self, outra):
        """Distância em km até outra empresa, ou None se não der para calcular."""
        if self.ponto and outra.ponto:
            return distancia_km(self.ponto, outra.ponto)
        return None

    def __str__(self):
        return self.nome
