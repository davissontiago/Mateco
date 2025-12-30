import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse 
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

# Importações locais do projeto
from .models import NotaFiscal, Empresa
from estoque.models import Produto
from .utils import simular_carrinho_inteligente
from .services import NuvemFiscalService 

# ==================================================
# FUNÇÃO AUXILIAR DE SEGURANÇA
# ==================================================
def get_empresa_usuario(request):
    """
    Recupera a empresa vinculada ao usuário logado.
    Se o usuário não tiver empresa (ex: admin esqueceu de vincular), retorna None.
    """
    try:
        # O 'perfil' vem do related_name que definimos no models.py
        return request.user.perfil.empresa
    except AttributeError:
        return None

# ==================================================
# 1. VIEWS DE NAVEGAÇÃO (PÁGINAS HTML)
# ==================================================

@login_required
def home(request):
    empresa = get_empresa_usuario(request)
    return render(request, 'index.html', {'empresa': empresa})

@login_required
def emitir(request):
    empresa = get_empresa_usuario(request)
    return render(request, 'emitir.html', {'empresa': empresa})

@login_required
def listar_notas(request):
    empresa = get_empresa_usuario(request)
    if not empresa:
        return render(request, 'notas.html', {'error': 'Usuário sem empresa vinculada.'})

    # FILTRAGEM: Traz apenas as notas da empresa do usuário
    notas = NotaFiscal.objects.filter(empresa=empresa).order_by('-data_emissao')
    
    return render(request, 'notas.html', {'notas': notas, 'empresa': empresa})

# ==================================================
# 2. VIEWS DE API (SERVIÇOS PARA O FRONTEND)
# ==================================================

@login_required 
def buscar_produtos(request):
    empresa = get_empresa_usuario(request)
    if not empresa:
        return JsonResponse({'error': 'Usuário sem empresa configurada'}, status=403)

    # 1. Modo Simulação (Carrinho Inteligente)
    if request.GET.get('simular') == 'true':
        try: 
            valor = float(request.GET.get('valor', 0))
        except (ValueError, TypeError): 
            return JsonResponse({'error': 'Valor inválido'}, status=400)
            
        # FILTRAGEM: Busca apenas produtos da minha empresa que tenham preço
        produtos = list(Produto.objects.filter(empresa=empresa, preco__gt=0).order_by('preco'))
        
        if not produtos: 
            return JsonResponse({'error': 'Sem produtos cadastrados nesta loja'}, status=404)
            
        lista, total = simular_carrinho_inteligente(valor, produtos)
        return JsonResponse({'itens': lista, 'total': round(total, 2)})

    # 2. Modo Busca Manual (Autocomplete)
    termo = request.GET.get('q', '')
    if termo:
        # FILTRAGEM: Busca produtos da empresa com nome parecido
        prods = Produto.objects.filter(empresa=empresa, nome__icontains=termo)[:10]
        
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
    empresa = get_empresa_usuario(request)
    
    # SEGURANÇA: Garante que só posso baixar notas da MINHA empresa
    nota = get_object_or_404(NotaFiscal, id=nota_id, empresa=empresa)
    
    if not nota.id_nota:
        return JsonResponse({'error': 'Nota sem ID da Nuvem Fiscal.'}, status=404)

    # ATENÇÃO: Aqui ainda estamos usando as credenciais do .env (Passo 5 vai corrigir isso)
    pdf_content, erro_msg = NuvemFiscalService.baixar_pdf(empresa, nota.id_nota)
    
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="nota_{nota.numero}.pdf"'
        return response
    
    return JsonResponse({'error': f'Falha ao baixar PDF: {erro_msg}'}, status=400)

@login_required
@csrf_exempt
def emitir_nota(request):
    empresa = get_empresa_usuario(request)
    if not empresa:
        return JsonResponse({'mensagem': 'Usuário sem empresa vinculada!'}, status=403)

    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            itens = dados.get('itens', [])
            forma_pagamento = dados.get('forma_pagamento', '01')
            
            if not itens: 
                return JsonResponse({'mensagem': 'Carrinho vazio'}, status=400)
            
            # --- ATENÇÃO ---
            # No próximo passo, vamos passar o objeto 'empresa' para este serviço
            # para que ele use o CNPJ e Token corretos.
            # Por enquanto, ele ainda vai ler do .env (Monolítico)
            sucesso, resultado, valor = NuvemFiscalService.emitir_nfce(empresa, itens, forma_pagamento)

            if sucesso:
                # Cria o registro local vinculado à empresa correta
                nota = NotaFiscal.objects.create(
                    empresa=empresa,  # <--- VÍNCULO IMPORTANTE
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