from django.conf import settings

from . import servico


def ia(request):
    ativa = servico.disponivel()
    # em desenvolvimento, avisa por que os botões de IA não aparecem
    return {'ia_ativa': ativa, 'ia_dica': settings.DEBUG and not ativa}
