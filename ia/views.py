import json
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from negociacoes.models import Negociacao

from . import servico


def _corpo(request):
    try:
        dados = json.loads(request.body or '{}')
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


def api_ia(view):
    """Exige POST, login e empresa; aplica o limite por hora; devolve erros em JSON."""

    @wraps(view)
    @require_POST
    def interna(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'erro': 'Entre na sua conta para usar a IA.'}, status=401)
        empresa = getattr(request.user, 'empresa', None)
        if empresa is None:
            return JsonResponse({'erro': 'Esta conta não tem uma empresa vinculada.'}, status=403)
        request.empresa = empresa
        if not servico.disponivel():
            return JsonResponse({'erro': 'A IA não está ativada neste servidor.'}, status=503)
        try:
            servico.checar_limite(request.user)
        except servico.LimiteExcedido:
            return JsonResponse({'erro': 'Você usou a IA muitas vezes nesta hora. Tente mais tarde.'}, status=429)
        try:
            return view(request, *args, **kwargs)
        except servico.IAIndisponivel as erro:
            return JsonResponse({'erro': str(erro)}, status=503)
        except servico.IAErro as erro:
            return JsonResponse({'erro': str(erro)}, status=502)

    return interna


@api_ia
def preencher_material(request):
    texto = str(_corpo(request).get('texto') or '').strip()
    if len(texto) < 10:
        return JsonResponse({'erro': 'Descreva o material em pelo menos uma frase.'}, status=400)
    if len(texto) > 1000:
        return JsonResponse({'erro': 'Use no máximo 1000 caracteres.'}, status=400)
    campos = servico.extrair_anuncio(texto)
    return JsonResponse({'campos': campos})


@api_ia
def sugerir_mensagem(request, pk):
    neg = (
        Negociacao.objects.select_related('material__empresa', 'proponente', 'ultima_alteracao_por')
        .filter(pk=pk).first()
    )
    # quem não participa recebe o mesmo 404 de uma negociação que não existe
    if neg is None or not neg.participa(request.empresa):
        return JsonResponse({'erro': 'Negociação não encontrada.'}, status=404)
    if not neg.ativa:
        return JsonResponse({'erro': 'Esta negociação está encerrada.'}, status=400)
    instrucao = str(_corpo(request).get('instrucao') or '').strip()[:200]
    texto = servico.sugerir_mensagem(neg, request.empresa, instrucao)
    return JsonResponse({'texto': texto})
