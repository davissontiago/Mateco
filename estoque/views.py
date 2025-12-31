from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Produto

@login_required
def listar_produtos(request):
    # 1. Segurança: Pega a empresa do usuário
    try:
        empresa = request.user.perfil.empresa
    except:
        return render(request, 'produtos.html', {'error': 'Usuário sem empresa vinculada.'})

    # 2. Captura termo de busca (se houver)
    termo = request.GET.get('q', '')

    # 3. Filtra produtos APENAS desta empresa
    if termo:
        produtos = Produto.objects.filter(
            empresa=empresa, 
            nome__icontains=termo
        ).order_by('nome')
    else:
        produtos = Produto.objects.filter(empresa=empresa).order_by('nome')

    # 4. Renderiza
    return render(request, 'produtos.html', {
        'produtos': produtos,
        'termo_busca': termo
    })