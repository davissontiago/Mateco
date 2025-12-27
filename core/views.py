# core/views.py
import json
import requests
from decouple import config
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import NotaFiscal        
from estoque.models import Produto   
from .utils import simular_carrinho_inteligente  

# --- VIEWS DE NAVEGAÇÃO ---

def home(request):
    return render(request, 'index.html')

def emitir(request):
    return render(request, 'emitir.html')

def listar_notas(request):
    notas = NotaFiscal.objects.all().order_by('-data_emissao')
    return render(request, 'notas.html', {'notas': notas})

def imprimir_nota(request, nota_id):
    nota = get_object_or_404(NotaFiscal, id=nota_id)
    if nota.url_pdf:
        return redirect(nota.url_pdf)
    return JsonResponse({'error': 'PDF não disponível'}, status=404)

# --- API: BUSCA E SIMULAÇÃO ---

def buscar_produtos(request):
    # 1. MODO SIMULAÇÃO (Inteligente)
    if request.GET.get('simular') == 'true':
        try:
            valor_alvo = float(request.GET.get('valor', 0))
        except ValueError:
            return JsonResponse({'error': 'Valor inválido'}, status=400)

        produtos_disponiveis = list(Produto.objects.filter(preco__gt=0).order_by('preco'))
        
        if not produtos_disponiveis:
            return JsonResponse({'error': 'Nenhum produto cadastrado!'}, status=404)

        # A mágica agora acontece no utils.py
        lista_simulada, total_final = simular_carrinho_inteligente(valor_alvo, produtos_disponiveis)

        return JsonResponse({
            'itens': lista_simulada,
            'total': round(total_final, 2)
        })

    # 2. MODO BUSCA MANUAL (Por Nome)
    termo = request.GET.get('q', '')
    if termo:
        # Busca produtos que contenham o nome (case insensitive)
        produtos = Produto.objects.filter(nome__icontains=termo).order_by('nome')[:10]
        resultados = []
        for p in produtos:
            resultados.append({
                'id': p.id,
                'nome': p.nome,
                'preco_unitario': float(p.preco),
                'ncm': p.ncm
            })
        return JsonResponse(resultados, safe=False)

    return JsonResponse([], safe=False)

# --- API: EMISSÃO DE NOTA FISCAL (Nuvem Fiscal) ---

@csrf_exempt
def emitir_nota(request):
    if request.method == 'POST':
        try:
            dados = json.loads(request.body)
            itens_carrinho = dados.get('itens', [])

            if not itens_carrinho:
                return JsonResponse({'mensagem': 'Carrinho vazio'}, status=400)

            # Prepara os itens para a API da Nuvem Fiscal
            itens_api = []
            valor_total_nota = 0.0

            for item in itens_carrinho:
                itens_api.append({
                    "codigo": str(item['id']),
                    "descricao": item['nome'],
                    "ncm": item.get('ncm', '00000000'),
                    "cest": "0100100",  # Exemplo, ideal vir do cadastro
                    "quantidade": item['quantidade'],
                    "unidade": "UN",
                    "valor_unitario": item['preco_unitario'],
                    "valor_total": item['valor_total']
                })
                valor_total_nota += item['valor_total']

            # Configurações da API
            url = "https://api.nuvemfiscal.com.br/v2/nfce"
            token = config('NUVEM_FISCAL_TOKEN')
            cnpj_emitente = config('CNPJ_EMITENTE')

            payload = {
                "ambiente": "homologacao", # Mude para 'producao' quando for valer
                "emitente": { "cnpj": cnpj_emitente },
                "itens": itens_api,
                "pagamento": {
                    "formas_pagamento": [{
                        "codigo_meio_pagamento": "01", # 01 = Dinheiro (Ajustar conforme necessidade)
                        "valor": valor_total_nota
                    }]
                }
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Envia para a Nuvem Fiscal
            response = requests.post(url, json=payload, headers=headers)
            resp_data = response.json()

            if response.status_code in [200, 201]:
                # Salva no banco local
                nota = NotaFiscal.objects.create(
                    numero=resp_data.get('numero', 0),
                    serie=resp_data.get('serie', 0),
                    chave=resp_data.get('chave', ''),
                    valor_total=valor_total_nota,
                    url_pdf=resp_data.get('url_danfe', ''),
                    url_xml=resp_data.get('url_xml', ''),
                    status='AUTORIZADA'
                )
                return JsonResponse({
                    'status': 'sucesso', 
                    'id_nota': nota.id, 
                    'url_pdf': nota.url_pdf
                })
            else:
                return JsonResponse({
                    'mensagem': f"Erro na API: {resp_data.get('error', {}).get('message', 'Desconhecido')}"
                }, status=400)

        except Exception as e:
            return JsonResponse({'mensagem': str(e)}, status=500)

    return JsonResponse({'mensagem': 'Método não permitido'}, status=405)