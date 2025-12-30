import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse 
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

# Importações locais do projeto
from .models import NotaFiscal
from estoque.models import Produto
from .utils import simular_carrinho_inteligente
from .services import NuvemFiscalService 

# ==================================================
# 1. VIEWS DE NAVEGAÇÃO (PÁGINAS HTML)
# ==================================================

@login_required
def home(request):
    """Renderiza a página inicial do Dashboard."""
    return render(request, 'index.html')

@login_required
def emitir(request):
    """Renderiza a tela de PDV para emissão de novas notas."""
    return render(request, 'emitir.html')

@login_required
def listar_notas(request):
    """
    Exibe o histórico de todas as notas fiscais emitidas.
    Ordenado pelas mais recentes.
    """
    notas = NotaFiscal.objects.all().order_by('-data_emissao')
    return render(request, 'notas.html', {'notas': notas})

# ==================================================
# 2. VIEWS DE API (SERVIÇOS PARA O FRONTEND)
# ==================================================

@login_required 
def buscar_produtos(request):
    """
    Endpoint para busca de produtos ou simulação de carrinho.
    
    Parâmetros GET:
    - q: Termo de busca por nome.
    - simular: 'true' para ativar o algoritmo de preenchimento automático.
    - valor: Valor alvo para a simulação.
    """
    # Lógica de Simulação Inteligente
    if request.GET.get('simular') == 'true':
        try: 
            valor = float(request.GET.get('valor', 0))
        except (ValueError, TypeError): 
            return JsonResponse({'error': 'Valor inválido'}, status=400)
            
        produtos = list(Produto.objects.filter(preco__gt=0).order_by('preco'))
        if not produtos: 
            return JsonResponse({'error': 'Sem produtos cadastrados'}, status=404)
            
        lista, total = simular_carrinho_inteligente(valor, produtos)
        return JsonResponse({'itens': lista, 'total': round(total, 2)})

    # Busca Simples por Termo
    termo = request.GET.get('q', '')
    if termo:
        prods = Produto.objects.filter(nome__icontains=termo)[:10]
        return JsonResponse([
            {
                'id': p.id, 
                'nome': p.nome, 
                'preco_unitario': float(p.preco), 
                'ncm': p.ncm
            } for p in prods
        ], safe=False)
        
    return JsonResponse([], safe=False)

# ==================================================
# 3. VIEWS DE EMISSÃO E DOWNLOAD
# ==================================================

@login_required
def imprimir_nota(request, nota_id):
    """
    Faz o download ou exibição do PDF da nota diretamente da Nuvem Fiscal.
    """
    nota = get_object_or_404(NotaFiscal, id=nota_id)
    
    if not nota.id_nota:
        return JsonResponse({'error': 'Nota sem ID da Nuvem Fiscal.'}, status=404)

    pdf_content, erro_msg = NuvemFiscalService.baixar_pdf(nota.id_nota)
    
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="nota_{nota.numero}.pdf"'
        return response
    
    return JsonResponse({'error': f'Falha ao baixar PDF: {erro_msg}'}, status=400)

@login_required
@csrf_exempt
def emitir_nota(request):
    """
    Processa a requisição POST do frontend para emitir a NFC-e.
    Comunica-se com NuvemFiscalService e salva o resultado no banco local.
    """
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            itens = dados.get('itens', [])
            forma_pagamento = dados.get('forma_pagamento', '01')
            
            if not itens: 
                return JsonResponse({'mensagem': 'Carrinho vazio'}, status=400)
            
            # Tenta emitir via API externa
            sucesso, resultado, valor = NuvemFiscalService.emitir_nfce(itens, forma_pagamento)

            if sucesso:
                # Cria o registro local da nota autorizada
                nota = NotaFiscal.objects.create(
                    id_nota=resultado.get('id'),
                    numero=resultado.get('numero', 0),
                    serie=resultado.get('serie', 0),
                    chave=resultado.get('chave', ''),
                    valor_total=valor,
                    status='AUTORIZADA'
                )
                return JsonResponse({'status': 'sucesso', 'id_nota': nota.id})
            else:
                return JsonResponse({'mensagem': f"Erro na API: {resultado}"}, status=400)

        except Exception as e:
            return JsonResponse({'mensagem': f"Erro interno: {str(e)}"}, status=500)
            
    return JsonResponse({'mensagem': 'Método não permitido'}, status=405)