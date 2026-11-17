from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FiltroForm, MaterialForm
from .match import combinacoes_para
from .models import Material

POR_PAGINA = 10


def home(request):
    recentes = Material.objects.filter(ativo=True).select_related('empresa')[:6]
    return render(request, 'home.html', {'recentes': recentes})


@login_required
def painel(request):
    empresa = request.user.empresa
    materiais = list(empresa.materiais.all())
    for m in materiais:
        # quantas combinações o sistema encontrou para cada anúncio ativo
        m.qtd_combinacoes = len(combinacoes_para(m, limite=50)) if m.ativo else 0
    return render(request, 'materiais/painel.html', {'empresa': empresa, 'materiais': materiais})


@login_required
def material_novo(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.empresa = request.user.empresa
            material.save()
            messages.success(request, 'Material cadastrado.')
            return redirect('painel')
    else:
        form = MaterialForm()
    return render(request, 'materiais/form.html', {'form': form, 'titulo': 'Novo material'})


@login_required
def material_editar(request, pk):
    # só a dona do anúncio consegue editar
    material = get_object_or_404(Material, pk=pk, empresa=request.user.empresa)
    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES, instance=material)
        if form.is_valid():
            form.save()
            messages.success(request, 'Alterações salvas.')
            return redirect('painel')
    else:
        form = MaterialForm(instance=material)
    return render(request, 'materiais/form.html', {'form': form, 'titulo': 'Editar material'})


@login_required
def material_excluir(request, pk):
    material = get_object_or_404(Material, pk=pk, empresa=request.user.empresa)
    if request.method == 'POST':
        material.delete()
        messages.success(request, 'Material excluído.')
        return redirect('painel')
    return render(request, 'materiais/excluir.html', {'material': material})


def material_detalhe(request, pk):
    material = get_object_or_404(Material.objects.select_related('empresa'), pk=pk, ativo=True)
    combinacoes = combinacoes_para(material)
    return render(request, 'materiais/detalhe.html', {
        'material': material,
        'combinacoes': combinacoes,
    })


def buscar(request):
    """Lista pública de anúncios com filtros e ordenação."""
    form = FiltroForm(request.GET)
    form.is_valid()  # todos os campos são opcionais
    filtros = form.cleaned_data

    anuncios = Material.objects.filter(ativo=True).select_related('empresa')
    if filtros.get('q'):
        termo = filtros['q']
        anuncios = anuncios.filter(Q(titulo__icontains=termo) | Q(descricao__icontains=termo))
    if filtros.get('intencao'):
        anuncios = anuncios.filter(intencao=filtros['intencao'])
    if filtros.get('categoria'):
        anuncios = anuncios.filter(categoria=filtros['categoria'])
    if filtros.get('modalidade'):
        anuncios = anuncios.filter(modalidade=filtros['modalidade'])
    if filtros.get('cidade'):
        anuncios = anuncios.filter(empresa__cidade__icontains=filtros['cidade'])
    if filtros.get('estado'):
        anuncios = anuncios.filter(empresa__estado__iexact=filtros['estado'])

    # distância até a empresa de quem está logado (quando dá para calcular)
    minha_empresa = getattr(request.user, 'empresa', None) if request.user.is_authenticated else None
    anuncios = list(anuncios)
    if minha_empresa:
        for m in anuncios:
            m.distancia = minha_empresa.distancia_ate(m.empresa)
    else:
        for m in anuncios:
            m.distancia = None

    if filtros.get('ordem') == 'proximos' and minha_empresa:
        # quem não tem distância calculável vai para o fim da lista
        anuncios.sort(key=lambda m: (m.distancia is None, m.distancia or 0))

    pagina = Paginator(anuncios, POR_PAGINA).get_page(request.GET.get('pagina'))

    # mantém os filtros nos links de paginação
    consulta = request.GET.copy()
    consulta.pop('pagina', None)
    so_filtros = consulta.copy()
    so_filtros.pop('ordem', None)

    return render(request, 'materiais/buscar.html', {
        'form': form,
        'pagina': pagina,
        'total': len(anuncios),
        'consulta': consulta.urlencode(),
        'tem_filtro': any(v for v in so_filtros.values()),
        'proximos_disponivel': bool(minha_empresa and minha_empresa.ponto),
    })
