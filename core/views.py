import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse # <--- Adicione HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import NotaFiscal
from estoque.models import Produto
from .utils import simular_carrinho_inteligente
from .services import NuvemFiscalService 

# ... (Home, Emitir, Listar Notas, Buscar Produtos IGUAIS) ...

def home(request): return render(request, 'index.html')
def emitir(request): return render(request, 'emitir.html')
def listar_notas(request):
    notas = NotaFiscal.objects.all().order_by('-data_emissao')
    return render(request, 'notas.html', {'notas': notas})
    
def buscar_produtos(request):
    # (Código igual ao anterior)
    if request.GET.get('simular') == 'true':
        try: valor = float(request.GET.get('valor', 0))
        except: return JsonResponse({'error': 'Valor inválido'}, status=400)
        produtos = list(Produto.objects.filter(preco__gt=0).order_by('preco'))
        if not produtos: return JsonResponse({'error': 'Sem produtos'}, 404)
        lista, total = simular_carrinho_inteligente(valor, produtos)
        return JsonResponse({'itens': lista, 'total': round(total, 2)})

    termo = request.GET.get('q', '')
    if termo:
        prods = Produto.objects.filter(nome__icontains=termo)[:10]
        return JsonResponse([{'id': p.id, 'nome': p.nome, 'preco_unitario': float(p.preco), 'ncm': p.ncm} for p in prods], safe=False)
    return JsonResponse([], safe=False)

# --- AQUI MUDA: Imprimir Nota buscando na hora ---
def imprimir_nota(request, nota_id):
    nota = get_object_or_404(NotaFiscal, id=nota_id)
    
    if not nota.id_nota:
        return JsonResponse({'error': 'Esta nota não possui ID da Nuvem Fiscal.'}, status=404)

    # Agora esperamos duas variáveis: o PDF e o Erro
    pdf_content, erro_msg = NuvemFiscalService.baixar_pdf(nota.id_nota)
    
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="nota_{nota.numero}.pdf"'
        return response
    
    # Se falhar, mostra o erro detalhado que veio da API
    return JsonResponse({'error': f'Falha ao baixar PDF: {erro_msg}'}, status=400)


# --- API Emitir (Sem os prints de debug agora) ---
@csrf_exempt
def emitir_nota(request):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            itens = dados.get('itens', [])
            forma_pagamento = dados.get('forma_pagamento', '01')
            if not itens: return JsonResponse({'mensagem': 'Carrinho vazio'}, status=400)

            sucesso, resultado, valor = NuvemFiscalService.emitir_nfce(itens, forma_pagamento)

            if sucesso:
                nota = NotaFiscal.objects.create(
                    id_nota=resultado.get('id'),
                    numero=resultado.get('numero', 0),
                    serie=resultado.get('serie', 0),
                    chave=resultado.get('chave', ''),
                    valor_total=valor,
                    url_pdf="", # Não salvamos mais URL, buscamos na hora
                    url_xml="",
                    status='AUTORIZADA'
                )
                return JsonResponse({'status': 'sucesso', 'id_nota': nota.id})
            else:
                return JsonResponse({'mensagem': f"Erro: {resultado}"}, status=400)

        except Exception as e:
            return JsonResponse({'mensagem': str(e)}, status=500)
    return JsonResponse({'mensagem': 'Método não permitido'}, status=405)