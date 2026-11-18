from .models import Negociacao


def pendencias(request):
    """Quantas negociações esperam uma ação da empresa logada (aparece no menu)."""
    usuario = request.user
    if not usuario.is_authenticated:
        return {}
    empresa = getattr(usuario, 'empresa', None)
    if empresa is None:
        return {}
    return {'qtd_pendencias': Negociacao.objects.pendentes_de(empresa).count()}
