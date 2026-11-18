from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import CadastroForm


def cadastro(request):
    if request.user.is_authenticated:
        return redirect('painel')

    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            usuario = form.salvar()
            login(request, usuario)
            messages.success(request, 'Conta criada! Agora cadastre o seu primeiro material.')
            return redirect('painel')
    else:
        form = CadastroForm()

    return render(request, 'contas/cadastro.html', {'form': form})
