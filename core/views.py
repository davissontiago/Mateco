import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q

# Importações locais do projeto
from .models import NotaFiscal, Empresa, Cliente
from .forms import ClienteForm, EmpresaConfigForm
from estoque.models import Produto
from .utils import simular_carrinho_inteligente
from .services import NuvemFiscalService
from .fiscal_router import FiscalRouter


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

@login_required
def emitir_nota_automatica(request):
    """
    Renderiza a tela exclusiva para emissão automática (Carrinho Inteligente).
    Como é sempre Consumidor Final, não buscamos clientes.
    """
    return render(request, 'emitir_auto.html')

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
        
    # ... código anterior ...
    totais = notas.aggregate(
        total_dinheiro=Sum('valor_total', filter=Q(forma_pagamento='01')),
        total_pix=Sum('valor_total', filter=Q(forma_pagamento='17')),
        total_debito=Sum('valor_total', filter=Q(forma_pagamento='04')),
        total_credito=Sum('valor_total', filter=Q(forma_pagamento='03')),
        total_geral=Sum('valor_total')
    )

    # --- NOVO: Cálculo seguro das percentagens ---
    total_geral = totais['total_geral'] or 0
    percentuais = {
        'dinheiro': ((totais['total_dinheiro'] or 0) / total_geral * 100) if total_geral > 0 else 0,
        'pix': ((totais['total_pix'] or 0) / total_geral * 100) if total_geral > 0 else 0,
        'debito': ((totais['total_debito'] or 0) / total_geral * 100) if total_geral > 0 else 0,
        'credito': ((totais['total_credito'] or 0) / total_geral * 100) if total_geral > 0 else 0,
    }

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
        'percentuais': percentuais, # <--- Envia os percentuais para o HTML
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
    nota = get_object_or_404(NotaFiscal, id=nota_id, empresa=empresa)

    # Nota SEFAZ direto: gera DANFE local a partir do XML autorizado.
    if not nota.id_nota:
        try:
            from core.danfe import gerar_danfe_nfce
            pdf_bytes = gerar_danfe_nfce(nota)
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="danfe_{nota.numero}.pdf"'
            return response
        except Exception as e:
            return JsonResponse({'error': f'Erro ao gerar DANFE: {str(e)}'}, status=500)

    pdf_content, erro_msg = NuvemFiscalService.baixar_pdf(empresa, nota.id_nota, ambiente=nota.ambiente)
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

    if request.method != 'POST':
        return JsonResponse({'mensagem': 'Método não permitido'}, status=405)

    try:
        dados = json.loads(request.body)
        itens = dados.get('itens', [])
        forma_pagamento = dados.get('forma_pagamento', '01')

        if not itens:
            return JsonResponse({'mensagem': 'Carrinho vazio'}, status=400)

        cliente_id = dados.get('cliente_id')
        cliente = None
        if cliente_id:
            cliente = Cliente.objects.filter(id=cliente_id, empresa=empresa).first()

        # Calcula total para montar pagamentos no formato unificado
        valor_calculado = sum(float(i.get('valor_total', 0)) for i in itens)
        pagamentos = [{'forma_pagamento': forma_pagamento, 'valor': round(valor_calculado, 2)}]

        sucesso, resultado, valor = FiscalRouter.emitir_nfce(
            empresa=empresa,
            itens_carrinho=itens,
            pagamentos=pagamentos,
            cliente=cliente,
        )

        if sucesso:
            nota = NotaFiscal.objects.create(
                empresa=empresa,
                cliente=cliente,
                forma_pagamento=forma_pagamento,
                id_nota=resultado.get('id') if empresa.emissor_fiscal == 'nuvem' else None,
                numero=resultado.get('numero', 0),
                serie=resultado.get('serie', 0),
                chave=resultado.get('chave', ''),
                valor_total=valor,
                status='AUTORIZADA',
                ambiente=empresa.ambiente,
                # campos SEFAZ direto (None quando NuvemFiscal)
                qrcode_url=resultado.get('qrcode_url') or None,
                xml_assinado=resultado.get('xml_protocolo') or None,
                protocolo_autorizacao=resultado.get('protocolo_autorizacao') or None,
            )
            return JsonResponse({'status': 'sucesso', 'id_nota': nota.id})
        else:
            return JsonResponse({'mensagem': f"Erro na emissão: {resultado}"}, status=400)

    except Exception as e:
        return JsonResponse({'mensagem': f"Erro interno: {str(e)}"}, status=500)

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
def configuracoes(request):
    """
    Página de configurações fiscais da empresa do usuário logado.
    Restrita a is_staff. Opera apenas sobre a empresa do próprio usuário
    (nunca aceita empresa_id da URL).
    """
    empresa = get_empresa_usuario(request)
    if not empresa:
        messages.error(request, "Usuário sem empresa vinculada.")
        return redirect('home')

    if request.method == 'POST':
        form = EmpresaConfigForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações salvas com sucesso!")
            return redirect('configuracoes')
        else:
            messages.error(request, "Corrija os erros abaixo.")
    else:
        form = EmpresaConfigForm(instance=empresa)

    # Metadados de certificado para exibição (nunca o conteúdo cifrado)
    cert_meta = {
        'hom_validade': empresa.certificado_a1_validade_homologacao,
        'hom_presente': bool(empresa.certificado_a1_pfx_homologacao),
        'prod_validade': empresa.certificado_a1_validade_producao,
        'prod_presente': bool(empresa.certificado_a1_pfx_producao),
        'csc_hom_presente': bool(empresa.csc_token_homologacao),
        'csc_prod_presente': bool(empresa.csc_token_producao),
    }

    return render(request, 'configuracoes.html', {
        'form': form,
        'empresa': empresa,
        'cert_meta': cert_meta,
    })


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