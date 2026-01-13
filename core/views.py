import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse 
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages  # <--- ADICIONE ESTA LINHA AQUI
from django.db.models import Sum

# Importações locais do projeto
from .models import NotaFiscal, Empresa, Cliente
from .forms import ClienteForm
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

def home(request):
    empresa = get_empresa_usuario(request)
    return render(request, 'index.html', {'empresa': empresa})

@login_required
def emitir(request):
    try:
        empresa = request.user.perfil.empresa
    except:
        return redirect('home')
        
    clientes = Cliente.objects.filter(empresa=empresa).order_by('nome')

    return render(request, 'emitir.html', {'clientes': clientes})

from django.db.models import Q

@login_required
def listar_notas(request):
    empresa = get_empresa_usuario(request)
    
    # Busca clientes para o filtro
    todos_clientes = Cliente.objects.filter(empresa=empresa).values('id', 'nome', 'apelido', 'cpf_cnpj').order_by('nome')
    
    # --- AQUI ESTAVA O ERRO: Adicionamos o filtro de ambiente ---
    notas = NotaFiscal.objects.filter(
        empresa=empresa, 
        ambiente=empresa.ambiente  # Garante que só apareçam notas do ambiente ativo
    ).select_related('cliente').order_by('-numero', '-serie')

    # --- LÓGICA DE FILTROS (Mantida igual) ---
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    filtro_clientes_ids = request.GET.getlist('clientes') 
    filtro_pagamentos = request.GET.getlist('pagamento')

    if data_inicio:
        notas = notas.filter(data_emissao__date__gte=data_inicio)
    if data_fim:
        notas = notas.filter(data_emissao__date__lte=data_fim)

    if filtro_clientes_ids:
        notas = notas.filter(cliente__id__in=filtro_clientes_ids)

    if filtro_pagamentos:
        notas = notas.filter(forma_pagamento__in=filtro_pagamentos)
        
    totais = notas.aggregate(
        total_dinheiro=Sum('valor_total', filter=Q(forma_pagamento='01')),
        total_pix=Sum('valor_total', filter=Q(forma_pagamento='17')),
        total_debito=Sum('valor_total', filter=Q(forma_pagamento='04')),
        total_credito=Sum('valor_total', filter=Q(forma_pagamento='03')),
        total_geral=Sum('valor_total')
    )

    context = {
        'notas': notas,
        'todos_clientes': todos_clientes,
        'filtros': {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'clientes': [int(x) for x in filtro_clientes_ids if x.isdigit()],
            'pagamento': filtro_pagamentos
        },
        'totais': totais,
    }
    return render(request, 'notas.html', context)

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
            
            cliente_id = dados.get('cliente_id') 
            cliente = None
            if cliente_id:
                # Busca o cliente e garante que é da mesma empresa (Segurança)
                cliente = Cliente.objects.filter(id=cliente_id, empresa=empresa).first()
                
            
            if not itens: 
                return JsonResponse({'mensagem': 'Carrinho vazio'}, status=400)
            
            sucesso, resultado, valor = NuvemFiscalService.emitir_nfce(empresa, itens, forma_pagamento, cliente=cliente)

            if sucesso:
                ambiente_usado = 'producao' if empresa.ambiente == 'producao' else 'homologacao'
                nota = NotaFiscal.objects.create(
                    empresa=empresa, 
                    cliente=cliente,
                    forma_pagamento=forma_pagamento,
                    id_nota=resultado.get('id'),
                    numero=resultado.get('numero', 0),
                    serie=resultado.get('serie', 0),
                    chave=resultado.get('chave', ''),
                    valor_total=valor,
                    status='AUTORIZADA',
                    ambiente=ambiente_usado
                )
                return JsonResponse({'status': 'sucesso', 'id_nota': nota.id})
            else:
                return JsonResponse({'mensagem': f"Erro na API: {resultado}"}, status=400)

        except Exception as e:
            return JsonResponse({'mensagem': f"Erro interno: {str(e)}"}, status=500)
            
    return JsonResponse({'mensagem': 'Método não permitido'}, status=405)

@login_required
def verificar_status_nota(request):
    """
    View utilitária para verificar se uma nota específica existe na SEFAZ/Nuvem.
    Pode ser chamada via URL: /verificar_nota/?numero=100&serie=2
    """
    empresa = get_empresa_usuario(request)
    numero = request.GET.get('numero')
    serie = request.GET.get('serie')
    
    if not numero or not serie:
        return JsonResponse({'erro': 'Informe numero e serie na URL'}, status=400)
        
    encontrada, dados = NuvemFiscalService.consultar_nota_por_numero(empresa, numero, serie)
    
    if encontrada:
        status_sefaz = dados.get('status')
        chave = dados.get('chave')
        return JsonResponse({
            'mensagem': 'NOTA ENCONTRADA NA NUVEM FISCAL!',
            'status': status_sefaz,
            'chave': chave,
            'id_nuvem': dados.get('id')
        })
    elif dados == "Nota não encontrada":
        return JsonResponse({'mensagem': 'Nota NÃO existe na Nuvem Fiscal. Pode emitir sem medo.'})
    else:
        return JsonResponse({'erro': dados}, status=500)

@login_required
def listar_clientes(request):
    try:
        empresa = request.user.perfil.empresa
    except:
        return redirect('home')

    termo = request.GET.get('q', '')
    
    if termo:
        clientes = Cliente.objects.filter(empresa=empresa, nome__icontains=termo).order_by('nome')
    else:
        clientes = Cliente.objects.filter(empresa=empresa).order_by('nome')

    return render(request, 'clientes.html', {'clientes': clientes, 'termo_busca': termo})

@login_required
def cadastrar_cliente(request, cliente_id=None): 
    try:
        empresa = request.user.perfil.empresa
    except:
        messages.error(request, "Usuário sem empresa vinculada.")
        return redirect('home')

    cliente = None
    if cliente_id:
        cliente = get_object_or_404(Cliente, id=cliente_id, empresa=empresa)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        
        if form.is_valid():
            obj = form.save(commit=False)
            obj.empresa = empresa
            obj.save()
            
            msg = f"Cliente {obj.nome} atualizado com sucesso!" if cliente_id else f"Cliente {obj.nome} cadastrado com sucesso!"
            messages.success(request, msg)
            return redirect('listar_clientes')
    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'form_clientes.html', {'form': form})