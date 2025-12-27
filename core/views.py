import json
import base64
import requests
import random
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from decouple import config
from .models import NotaFiscal
from estoque.models import Produto

# --- FUNÇÕES AUXILIARES ---

def pegar_token_acesso():
    client_id = config('NUVEM_CLIENT_ID')
    client_secret = config('NUVEM_CLIENT_SECRET')
    url = "https://auth.nuvemfiscal.com.br/oauth/token"
    credenciais = f"{client_id}:{client_secret}"
    credenciais_b64 = base64.b64encode(credenciais.encode()).decode()
    headers = {"Authorization": f"Basic {credenciais_b64}", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials", "scope": "nfce"}
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200: return response.json()['access_token']
    else: raise Exception(f"Erro Auth: {response.text}")

def gerar_nota_json(itens_recebidos):
    cnpj = config('CNPJ_EMITENTE')
    ie = config('IE_EMITENTE')
    
    lista_detalhes = []
    valor_total_nota = 0.0

    for i, item in enumerate(itens_recebidos):
        # Pega dados com suporte a quantidade
        preco_unit = float(item.get('preco_unitario', item.get('preco')))
        qtd = int(item.get('quantidade', 1))
        
        # Calcula total do item
        valor_item = round(preco_unit * qtd, 2)
        valor_total_nota += valor_item
        
        ncm_item = item.get('ncm', '25232910').replace('.', '')
        
        det = {
            "nItem": i + 1,
            "prod": {
                "cProd": str(item.get('id', 'GEN')),
                "cEAN": "SEM GTIN",
                "xProd": item['nome'],
                "NCM": ncm_item,
                "CFOP": "5102", "uCom": "UN", 
                "qCom": float(qtd),       # <--- Quantidade Sorteada
                "vUnCom": preco_unit,     # <--- Preço Unitário
                "vProd": valor_item,      # <--- Total do Item
                "cEANTrib": "SEM GTIN",
                "uTrib": "UN", "qTrib": float(qtd), "vUnTrib": preco_unit, "indTot": 1
            },
            "imposto": {
                "ICMS": { "ICMSSN102": { "orig": 0, "CSOSN": "102" } },
                "PIS": { "PISNT": { "CST": "07" } },
                "COFINS": { "COFINSNT": { "CST": "07" } }
            }
        }
        lista_detalhes.append(det)

    valor_total_nota = round(valor_total_nota, 2)

    return {
        "ambiente": "homologacao",
        "infNFe": {
            "versao": "4.00",
            "ide": {
                "cUF": 21,
                "cNF": str(random.randint(10000000, 99999999)),
                "natOp": "VENDA AO CONSUMIDOR",
                "mod": 65,
                "serie": 1,
                "nNF": random.randint(1, 99999),
                "dhEmi": datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00"),
                "tpNF": 1, "idDest": 1, "cMunFG": "2112209", "tpImp": 4, "tpEmis": 1,
                "cDV": random.randint(0, 9), "tpAmb": 2, "finNFe": 1,
                "indFinal": 1, "indPres": 1, "procEmi": 0, "verProc": "MatecoPDV 2.0"
            },
            "emit": { "CNPJ": cnpj, "IE": ie, "CRT": 1 },
            "det": lista_detalhes,
            "total": {
                "ICMSTot": {
                    "vBC": 0.00, "vICMS": 0.00, "vICMSDeson": 0.00, 
                    "vFCP": 0.00, "vBCST": 0.00, "vST": 0.00, 
                    "vFCPST": 0.00, "vFCPSTRet": 0.00,
                    "vProd": valor_total_nota, "vFrete": 0.00, "vSeg": 0.00, 
                    "vDesc": 0.00, "vII": 0.00, "vIPI": 0.00, "vIPIDevol": 0.00, 
                    "vPIS": 0.00, "vCOFINS": 0.00, "vOutro": 0.00, 
                    "vNF": valor_total_nota, "vTotTrib": 0.00
                }
            },
            "transp": { "modFrete": 9 },
            "pag": { "detPag": [ { "tPag": "01", "vPag": valor_total_nota } ] }
        }
    }

# --- VIEWS ---

def home(request):
    return render(request, 'index.html')

def emitir(request):
    return render(request, 'emitir.html')

def listar_notas(request):
    notas = NotaFiscal.objects.all()
    return render(request, 'notas.html', {'notas': notas})

# --- API: SIMULADOR INTELIGENTE COM QUANTIDADES ---
def buscar_produtos(request):
    if request.GET.get('simular') == 'true':
        try: valor_alvo = float(request.GET.get('valor', 0))
        except: return JsonResponse({'error': 'Valor inválido'}, status=400)

        produtos_disponiveis = list(Produto.objects.filter(preco__gt=0).order_by('preco'))
        if not produtos_disponiveis:
            return JsonResponse({'error': 'Nenhum produto com preço cadastrado!'}, status=404)

        lista_simulada = []
        total_atual = 0.0

        # CONFIGURAÇÃO DE PROBABILIDADE (PESOS)
        # Números: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        # Pesos:   1 tem chance 50, 2 tem 15, e vai caindo...
        opcoes_qtd = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        pesos_qtd  = [50, 15, 10, 5, 5, 3, 3, 3, 3, 3] 

        while total_atual < valor_alvo:
            falta = valor_alvo - total_atual
            
            # Filtra o que cabe (considerando pelo menos 1 unidade)
            produtos_que_cabem = [p for p in produtos_disponiveis if float(p.preco) <= falta]
            
            if produtos_que_cabem:
                prod = random.choice(produtos_que_cabem)
                preco = float(prod.preco)
                
                # Sorteia quantidade baseada nos pesos
                qtd_sorteada = random.choices(opcoes_qtd, weights=pesos_qtd, k=1)[0]
                
                # Verifica se a quantidade sorteada cabe no valor que falta
                # Ex: Sorteou 10, mas só faltam R$ 50 e o produto custa R$ 20. Só cabem 2.
                max_que_cabe = int(falta // preco)
                
                # Usa o menor valor (mas garante pelo menos 1)
                quantidade_final = min(qtd_sorteada, max_que_cabe)
                if quantidade_final < 1: quantidade_final = 1
                
            else:
                # Se nada cabe, pega o mais barato (1 unidade) para fechar
                prod = produtos_disponiveis[0] 
                preco = float(prod.preco)
                quantidade_final = 1

            total_item = preco * quantidade_final
            
            lista_simulada.append({
                'id': prod.id,
                'nome': prod.nome,
                'preco_unitario': preco,
                'quantidade': quantidade_final,
                'valor_total': total_item,
                'ncm': prod.ncm
            })
            total_atual += total_item
        
        return JsonResponse({
            'itens': lista_simulada,
            'total': round(total_atual, 2)
        })

    return JsonResponse([], safe=False)

def emitir_nfce_view(request):
    if request.method == "POST":
        try:
            token = pegar_token_acesso()
            body = json.loads(request.body)
            itens = body.get('itens')
            
            if not itens: return JsonResponse({"status": "erro", "mensagem": "Lista vazia"}, status=400)

            # Recalcula total final
            valor_total_real = sum(float(i['valor_total']) for i in itens)

            payload = gerar_nota_json(itens)
            url_emissao = "https://api.sandbox.nuvemfiscal.com.br/nfce"
            headers = { "Authorization": f"Bearer {token}", "Content-Type": "application/json" }
            
            resp = requests.post(url_emissao, headers=headers, json=payload)
            
            if resp.status_code == 200:
                dados = resp.json()
                NotaFiscal.objects.create(
                    id_nota=dados.get('id'), numero=dados.get('numero'),
                    serie=dados.get('serie'), valor=valor_total_real, status=dados.get('status')
                )
                return JsonResponse({"status": "sucesso", "mensagem": "Nota autorizada!", "id_nota": dados.get('id'), "valor": valor_total_real})
            else:
                return JsonResponse({"status": "erro", "mensagem": resp.text}, status=400)
        except Exception as e:
            return JsonResponse({"status": "erro", "mensagem": str(e)}, status=500)
    return JsonResponse({"status": "erro", "mensagem": "Método inválido"}, status=405)

def baixar_pdf_view(request, id_nota):
    try:
        token = pegar_token_acesso()
        url = f"https://api.sandbox.nuvemfiscal.com.br/nfce/{id_nota}/pdf"
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            return HttpResponse(resp.content, content_type='application/pdf')
        else:
            return HttpResponse(f"Erro PDF: {resp.text}", status=400)
    except Exception as e:
        return HttpResponse(f"Erro interno: {str(e)}", status=500)