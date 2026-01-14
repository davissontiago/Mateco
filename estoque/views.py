from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Produto
from .forms import ProdutoForm
from core.services import get_empresa_usuario
from core.utils import simular_carrinho_inteligente

# ==================================================
# 1. VIEWS DE PÁGINA (HTML) - Catálogo e CRUD
# ==================================================

@login_required
def listar_produtos(request):
    """
    Exibe a lista de produtos com filtros de busca e estoque.
    """
    empresa = get_empresa_usuario(request)
    produtos = Produto.objects.filter(empresa=empresa).order_by('nome')

    # Filtro de Texto
    termo_busca = request.GET.get('q')
    if termo_busca:
        produtos = produtos.filter(
            Q(nome__icontains=termo_busca) |
            Q(codigo__icontains=termo_busca) |
            Q(ncm__icontains=termo_busca)
        )

    # Filtro de Estoque
    filtro_estoque = request.GET.get('filtro_estoque')
    if filtro_estoque == 'positivo':
        produtos = produtos.filter(estoque_atual__gt=0)
    elif filtro_estoque == 'zerado':
        produtos = produtos.filter(estoque_atual__lte=0)
    elif filtro_estoque == 'baixo':
        produtos = produtos.filter(estoque_atual__lte=5, estoque_atual__gt=0)

    context = {
        'produtos': produtos,
        'termo_busca': termo_busca,
        'filtro_estoque': filtro_estoque
    }
    return render(request, 'produtos.html', context)

@login_required
def criar_produto(request):
    empresa = get_empresa_usuario(request)
    
    if request.method == 'POST':
        form = ProdutoForm(request.POST)
        if form.is_valid():
            produto = form.save(commit=False)
            produto.empresa = empresa # Vincula à empresa do usuário
            produto.save()
            messages.success(request, 'Produto criado com sucesso!')
            return redirect('listar_produtos')
    else:
        form = ProdutoForm()

    return render(request, 'form_produto.html', {'form': form})

@login_required
def editar_produto(request, id):
    empresa = get_empresa_usuario(request)
    # Garante que só edita produtos da própria empresa
    produto = get_object_or_404(Produto, id=id, empresa=empresa)
    
    if request.method == 'POST':
        form = ProdutoForm(request.POST, instance=produto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto atualizado com sucesso!')
            return redirect('listar_produtos')
    else:
        form = ProdutoForm(instance=produto)

    return render(request, 'form_produto.html', {'form': form})

@login_required
def deletar_produto(request, id):
    empresa = get_empresa_usuario(request)
    # Garante que só deleta produtos da própria empresa
    produto = get_object_or_404(Produto, id=id, empresa=empresa)
    
    if request.method == 'POST':
        produto.delete()
        messages.success(request, 'Produto excluído com sucesso!')
        return redirect('listar_produtos')
        
    return redirect('listar_produtos')

# ==================================================
# 2. APIs JSON (USADAS PELO JAVASCRIPT / EMITIR.JS)
# ==================================================

@login_required 
def buscar_produtos(request):
    """
    API para busca dinâmica (Autocomplete) e simulação de carrinho.
    ESSENCIAL para a tela de emissão de notas.
    """
    empresa = get_empresa_usuario(request)
    if not empresa:
        return JsonResponse({'error': 'Usuário sem empresa configurada'}, status=403)

    # Modo Simulação (Carrinho Inteligente)
    if request.GET.get('simular') == 'true':
        try: 
            valor = float(request.GET.get('valor', 0))
        except (ValueError, TypeError): 
            return JsonResponse({'error': 'Valor inválido'}, status=400)
            
        produtos = list(Produto.objects.filter(empresa=empresa, preco__gt=0).order_by('preco'))
        
        if not produtos: 
            return JsonResponse({'error': 'Sem produtos cadastrados nesta loja'}, status=404)
            
        lista, total = simular_carrinho_inteligente(valor, produtos)
        return JsonResponse({'itens': lista, 'total': round(total, 2)})

    # Modo Busca Normal (Autocomplete)
    # Aceita 'q' (do select2) ou 'termo' (do autocomplete antigo)
    termo = request.GET.get('q', request.GET.get('termo', ''))
    
    if termo:
        produtos = Produto.objects.filter(
            Q(nome__icontains=termo) | 
            Q(codigo__icontains=termo),
            empresa=empresa
        )[:20]
    else:
        produtos = []
    
    data = [{
        'id': p.id, 
        'nome': p.nome, 
        'preco_unitario': p.preco, 
        'estoque': p.estoque_atual,
        'ncm': p.ncm
    } for p in produtos]
    
    return JsonResponse(data, safe=False)