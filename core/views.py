import json
import base64
import requests
import random
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from decouple import config
from .models import NotaFiscal

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

def gerar_nota_json(valor_total):
    cnpj = config('CNPJ_EMITENTE')
    ie = config('IE_EMITENTE')
    
    lista_detalhes = [{
        "nItem": 1,
        "prod": {
            "cProd": "GEN001",
            "cEAN": "SEM GTIN",
            "xProd": "PRODUTO GENERICO DIVERSOS",
            "NCM": "25232910", "CFOP": "5102", "uCom": "UN", "qCom": 1.0,
            "vUnCom": valor_total, "vProd": valor_total, "cEANTrib": "SEM GTIN",
            "uTrib": "UN", "qTrib": 1.0, "vUnTrib": valor_total, "indTot": 1
        },
        "imposto": {
            "ICMS": { "ICMSSN102": { "orig": 0, "CSOSN": "102" } },
            "PIS": { "PISNT": { "CST": "07" } },
            "COFINS": { "COFINSNT": { "CST": "07" } }
        }
    }]

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
                # CORREÇÃO AQUI: Adicionados todos os campos obrigatórios zerados
                "ICMSTot": {
                    "vBC": 0.00, "vICMS": 0.00, "vICMSDeson": 0.00, 
                    "vFCP": 0.00, "vBCST": 0.00, "vST": 0.00, 
                    "vFCPST": 0.00, "vFCPSTRet": 0.00,
                    "vProd": valor_total, 
                    "vFrete": 0.00, "vSeg": 0.00, "vDesc": 0.00,
                    "vII": 0.00, "vIPI": 0.00, "vIPIDevol": 0.00, 
                    "vPIS": 0.00, "vCOFINS": 0.00, "vOutro": 0.00, 
                    "vNF": valor_total, "vTotTrib": 0.00
                }
            },
            "transp": { "modFrete": 9 },
            "pag": { "detPag": [ { "tPag": "01", "vPag": valor_total } ] }
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

def emitir_nfce_view(request):
    if request.method == "POST":
        try:
            token = pegar_token_acesso()
            
            # --- VOLTA A RECEBER APENAS O VALOR ---
            body = json.loads(request.body)
            try:
                valor_total = float(body.get('valor', 0))
            except:
                return JsonResponse({"status": "erro", "mensagem": "Valor inválido"}, status=400)
            
            if valor_total <= 0:
                return JsonResponse({"status": "erro", "mensagem": "Valor deve ser maior que zero"}, status=400)

            payload = gerar_nota_json(valor_total)
            # --------------------------------------

            url_emissao = "https://api.sandbox.nuvemfiscal.com.br/nfce"
            headers = { "Authorization": f"Bearer {token}", "Content-Type": "application/json" }
            
            resp = requests.post(url_emissao, headers=headers, json=payload)
            
            if resp.status_code == 200:
                dados = resp.json()
                NotaFiscal.objects.create(
                    id_nota=dados.get('id'),
                    numero=dados.get('numero'),
                    serie=dados.get('serie'),
                    valor=valor_total,
                    status=dados.get('status')
                )
                return JsonResponse({"status": "sucesso", "mensagem": "Nota autorizada!", "id_nota": dados.get('id'), "valor": valor_total})
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