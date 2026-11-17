from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def empresa_obrigatoria(view):
    """Exige login e uma empresa vinculada ao usuário; coloca a empresa em request.empresa.

    Usuários criados só pelo admin (sem perfil de empresa) são avisados em vez de
    causar erro na página.
    """

    @wraps(view)
    @login_required
    def interna(request, *args, **kwargs):
        empresa = getattr(request.user, 'empresa', None)
        if empresa is None:
            messages.error(request, 'Esta conta não tem uma empresa vinculada. Crie uma conta de empresa para continuar.')
            return redirect('home')
        request.empresa = empresa
        return view(request, *args, **kwargs)

    return interna
