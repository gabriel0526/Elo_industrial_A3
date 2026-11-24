from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from contas.decorators import empresa_obrigatoria
from materiais.models import Material

from . import resultados as calculo
from .forms import MensagemForm, PropostaForm, TermosForm
from .models import AcaoInvalida, Negociacao, Recibo


def _carregar(request, pk):
    """Busca a negociação e garante que só as duas empresas envolvidas acessem."""
    neg = get_object_or_404(
        Negociacao.objects.select_related('material__empresa', 'proponente', 'ultima_alteracao_por'),
        pk=pk,
    )
    if not neg.participa(request.empresa):
        raise Http404
    return neg


@empresa_obrigatoria
def lista(request):
    empresa = request.empresa
    negociacoes = list(
        Negociacao.objects.da_empresa(empresa).select_related(
            'material__empresa', 'proponente', 'recibo'
        )
    )
    for n in negociacoes:
        n.outra = n.outra_parte(empresa)
        n.vez_de_mim = n.ativa and n.vez_de(empresa)
    return render(request, 'negociacoes/lista.html', {
        'aguardando': [n for n in negociacoes if n.ativa and n.vez_de(empresa)],
        'andamento': [n for n in negociacoes if n.ativa and not n.vez_de(empresa)],
        'encerradas': [n for n in negociacoes if not n.ativa],
    })


@empresa_obrigatoria
def nova(request, material_pk):
    material = get_object_or_404(Material.objects.select_related('empresa'), pk=material_pk, ativo=True)
    empresa = request.empresa

    if material.empresa_id == empresa.pk:
        messages.error(request, 'Você não pode negociar com o seu próprio anúncio.')
        return redirect('material_detalhe', pk=material.pk)

    existente = Negociacao.objects.filter(
        material=material, proponente=empresa, status__in=[Negociacao.ABERTA, Negociacao.ACEITA]
    ).first()
    if existente:
        messages.info(request, 'Você já tem uma negociação aberta neste anúncio.')
        return redirect('negociacao_detalhe', pk=existente.pk)

    if request.method == 'POST':
        form = PropostaForm(request.POST, material=material)
        if form.is_valid():
            neg = form.save(commit=False)
            neg.material = material
            neg.proponente = empresa
            neg.ultima_alteracao_por = empresa
            neg.save()
            neg.registrar(f'{empresa.nome} enviou uma proposta: {neg.resumo()}.')
            if form.cleaned_data['mensagem']:
                neg.registrar(form.cleaned_data['mensagem'], autor=empresa)
            messages.success(request, 'Proposta enviada. Agora é só aguardar a resposta.')
            return redirect('negociacao_detalhe', pk=neg.pk)
    else:
        form = PropostaForm(
            material=material,
            initial={
                'quantidade': material.quantidade,
                'preco': material.preco,
                'modalidade': 'doacao' if material.modalidade == 'doacao' else 'venda',
            },
        )
    return render(request, 'negociacoes/nova.html', {'form': form, 'material': material})


@empresa_obrigatoria
def detalhe(request, pk):
    neg = _carregar(request, pk)
    empresa = request.empresa
    return render(request, 'negociacoes/detalhe.html', {
        'neg': neg,
        'outra': neg.outra_parte(empresa),
        'papel': neg.papel_de(empresa),
        'minha_vez': neg.vez_de(empresa),
        'ja_confirmei': neg.confirmou(empresa),
        'mensagens': neg.mensagens.select_related('autor'),
        'form_mensagem': MensagemForm(),
    })


@empresa_obrigatoria
def alterar(request, pk):
    neg = _carregar(request, pk)
    if neg.status != Negociacao.ABERTA:
        messages.error(request, 'Só dá para alterar os termos enquanto a negociação está aberta.')
        return redirect('negociacao_detalhe', pk=neg.pk)

    if request.method == 'POST':
        form = TermosForm(request.POST, instance=neg, material=neg.material)
        if form.is_valid():
            dados = form.cleaned_data
            # ao validar, o form já colocou os novos valores na instância (ainda sem salvar),
            # então neg.resumo() descreve os termos novos
            try:
                neg.alterar_termos(
                    request.empresa, dados['quantidade'], dados['preco'],
                    dados['modalidade'], dados['retirada'], neg.resumo(),
                )
            except AcaoInvalida as erro:
                messages.error(request, str(erro))
            else:
                messages.success(request, 'Termos atualizados. A outra empresa precisa aceitar.')
            return redirect('negociacao_detalhe', pk=neg.pk)
    else:
        form = TermosForm(instance=neg, material=neg.material)
    return render(request, 'negociacoes/alterar.html', {'form': form, 'neg': neg})


@empresa_obrigatoria
@require_POST
def mensagem(request, pk):
    neg = _carregar(request, pk)
    if not neg.ativa:
        messages.error(request, 'Esta negociação está encerrada, não dá mais para enviar mensagens.')
        return redirect('negociacao_detalhe', pk=neg.pk)
    form = MensagemForm(request.POST)
    if form.is_valid():
        neg.registrar(form.cleaned_data['texto'], autor=request.empresa)
        neg.save()  # atualiza "atualizada_em" para a negociação subir na lista
    else:
        messages.error(request, 'Escreva uma mensagem de até 1000 caracteres.')
    return redirect('negociacao_detalhe', pk=neg.pk)


def _acao(request, pk, metodo, sucesso):
    neg = _carregar(request, pk)
    try:
        getattr(neg, metodo)(request.empresa)
    except AcaoInvalida as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, sucesso)
    return redirect('negociacao_detalhe', pk=neg.pk)


@empresa_obrigatoria
@require_POST
def aceitar(request, pk):
    return _acao(request, pk, 'aceitar', 'Proposta aceita.')


@empresa_obrigatoria
@require_POST
def encerrar(request, pk):
    return _acao(request, pk, 'encerrar', 'Negociação encerrada.')


@empresa_obrigatoria
@require_POST
def confirmar(request, pk):
    return _acao(request, pk, 'confirmar_entrega', 'Confirmação registrada.')


@empresa_obrigatoria
def recibo(request, pk):
    recibo = get_object_or_404(
        Recibo.objects.select_related('negociacao__material__empresa', 'negociacao__proponente'), pk=pk
    )
    if not recibo.negociacao.participa(request.empresa):
        raise Http404
    return render(request, 'negociacoes/recibo.html', {'recibo': recibo})


# ---------- painel de resultados (Etapa 5) ----------
def _periodo(request):
    chave = request.GET.get('periodo', calculo.PERIODO_PADRAO)
    return chave if chave in calculo.PERIODOS else calculo.PERIODO_PADRAO


@empresa_obrigatoria
def resultados(request):
    empresa = request.empresa
    periodo = _periodo(request)

    custo_texto = request.GET.get('custo', '').strip()
    custo = calculo.ler_valor(custo_texto)
    if custo_texto and custo is None:
        messages.error(request, 'Não entendi o valor por tonelada. Use um número, por exemplo 180,50.')

    negociacoes = calculo.concluidas(empresa, periodo)
    recentes = negociacoes[:10]
    for n in recentes:
        n.outra = n.outra_parte(empresa)
    return render(request, 'negociacoes/resultados.html', {
        'dados': calculo.calcular(empresa, negociacoes, custo),
        'periodos': [(chave, rotulo) for chave, (rotulo, _) in calculo.PERIODOS.items()],
        'periodo': periodo,
        'periodo_rotulo': calculo.PERIODOS[periodo][0],
        'custo_texto': custo_texto if custo else '',
        'recentes': recentes,
        'total_concluidas': len(negociacoes),
    })


@empresa_obrigatoria
def resultados_exportar(request):
    empresa = request.empresa
    negociacoes = calculo.concluidas(empresa, _periodo(request))
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = 'attachment; filename="elo-industrial-historico.csv"'
    resposta.write('\ufeff')  # marca de UTF-8 para o Excel mostrar os acentos certos
    calculo.escrever_csv(resposta, empresa, negociacoes)
    return resposta
