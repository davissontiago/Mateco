import json
import base64
import requests
import random
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from decouple import config

# --- FUNÇÕES AUXILIARES (Lógica de Negócio) ---

def pegar_token_acesso():
    """Autentica na Nuvem Fiscal e retorna o Token"""
    client_id = config('NUVEM_CLIENT_ID')
    client_secret = config('NUVEM_CLIENT_SECRET')
    
    url = "https://auth.nuvemfiscal.com.br/oauth/token"
    credenciais = f"{client_id}:{client_secret}"
    credenciais_b64 = base64.b64encode(credenciais.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {credenciais_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials", "scope": "nfce"}
    
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise Exception(f"Erro Auth: {response.text}")

def gerar_nota_json(valor_total):
    """Monta o JSON da Nota Fiscal"""
    cnpj = config('CNPJ_EMITENTE')
    ie = config('IE_EMITENTE')
    
    # Exemplo: Divide o valor total em 2 itens para teste
    item_preco = valor_total / 2 
    
    lista_detalhes = []
    for i in range(1, 3): # Cria 2 itens
        det = {
            "nItem": i,
            "prod": {
                "cProd": f"00{i}",
                "cEAN": "SEM GTIN",
                "xProd": f"PRODUTO TESTE {i}",
                "NCM": "25232910", # NCM de Cimento (Exemplo)
                "CFOP": "5102",
                "uCom": "UN",
                "qCom": 1.0,
                "vUnCom": item_preco,
                "vProd": item_preco,
                "cEANTrib": "SEM GTIN",
                "uTrib": "UN",
                "qTrib": 1.0,
                "vUnTrib": item_preco,
                "indTot": 1
            },
            "imposto": {
                "ICMS": { "ICMSSN102": { "orig": 0, "CSOSN": "102" } },
                "PIS": { "PISNT": { "CST": "07" } },
                "COFINS": { "COFINSNT": { "CST": "07" } }
            }
        }
        lista_detalhes.append(det)

    payload = {
        "ambiente": "homologacao",
        "infNFe": {
            "versao": "4.00",
            "ide": {
                "cUF": 21, # MA (Maranhão)
                "cNF": str(random.randint(10000000, 99999999)),
                "natOp": "VENDA AO CONSUMIDOR",
                "mod": 65,
                "serie": 1,
                "nNF": random.randint(1, 99999),
                "dhEmi": datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00"),
                "tpNF": 1,
                "idDest": 1,
                "cMunFG": "2112209", # Código IBGE de Timon-MA
                "tpImp": 4,
                "tpEmis": 1,
                "cDV": random.randint(0, 9),
                "tpAmb": 2, # Homologação
                "finNFe": 1,
                "indFinal": 1,
                "indPres": 1,
                "procEmi": 0,
                "verProc": "MatecoPDV 1.0"
            },
            "emit": { "CNPJ": cnpj, "IE": ie, "CRT": 1 },
            "det": lista_detalhes,
            "total": {
                "ICMSTot": {
                    "vBC": 0.00, "vICMS": 0.00, "vICMSDeson": 0.00, "vFCP": 0.00,
                    "vBCST": 0.00, "vST": 0.00, "vFCPST": 0.00, "vFCPSTRet": 0.00,
                    "vProd": valor_total, "vFrete": 0.00, "vSeg": 0.00, "vDesc": 0.00,
                    "vII": 0.00, "vIPI": 0.00, "vIPIDevol": 0.00, "vPIS": 0.00,
                    "vCOFINS": 0.00, "vOutro": 0.00, "vNF": valor_total, "vTotTrib": 0.00
                }
            },
            "transp": { "modFrete": 9 },
            "pag": { "detPag": [ { "tPag": "01", "vPag": valor_total } ] }
        }
    }
    return payload

# --- VIEWS DO DJANGO (Rotas) ---

def home(request):
    """Página Inicial"""
    return render(request, 'index.html')

def pdv(request):
    """Tela de Vendas"""
    return render(request, 'pdv.html')

def emitir_nfce_view(request):
    """
    Rota API: Recebe o pedido do botão e emite a nota
    """
    if request.method == "POST":
        try:
            token = pegar_token_acesso()
            
            # Tenta pegar valor do JSON enviado pelo JS, se não houver, usa 100
            try:
                body = json.loads(request.body)
                valor = float(body.get('valor', 100))
            except:
                valor = 100.00
            
            payload = gerar_nota_json(valor)
            
            url_emissao = "https://api.sandbox.nuvemfiscal.com.br/nfce"
            headers = { "Authorization": f"Bearer {token}", "Content-Type": "application/json" }
            
            resp = requests.post(url_emissao, headers=headers, json=payload)
            
            if resp.status_code == 200:
                dados = resp.json()
                return JsonResponse({
                    "status": "sucesso", 
                    "mensagem": "Nota autorizada!",
                    "id_nota": dados.get('id')
                })
            else:
                return JsonResponse({"status": "erro", "mensagem": resp.text}, status=400)
        except Exception as e:
            return JsonResponse({"status": "erro", "mensagem": str(e)}, status=500)
    
    return JsonResponse({"status": "erro", "mensagem": "Método inválido"}, status=405)

def baixar_pdf_view(request, id_nota):
    """
    Rota Proxy: O Django baixa o PDF e entrega pro navegador
    Isso evita o erro de 'Não Autorizado' no link direto.
    """
    try:
        token = pegar_token_acesso()
        url = f"https://api.sandbox.nuvemfiscal.com.br/nfce/{id_nota}/pdf"
        headers = {"Authorization": f"Bearer {token}"}
        
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 200:
            # Retorna o PDF como se fosse um arquivo do próprio site
            return HttpResponse(resp.content, content_type='application/pdf')
        else:
            return HttpResponse(f"Erro ao baixar PDF da Nuvem Fiscal: {resp.text}", status=400)
            
    except Exception as e:
        return HttpResponse(f"Erro interno no servidor: {str(e)}", status=500)