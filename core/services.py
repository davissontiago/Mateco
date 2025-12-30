import requests
import base64
import json
from datetime import datetime
from decouple import config
from .models import NotaFiscal

class NuvemFiscalService:
    """
    Serviço responsável pela comunicação com a API da Nuvem Fiscal.
    
    Lida com autenticação OAuth2, montagem do payload da NFC-e,
    emissão de documentos e download de PDFs.
    """

    @staticmethod
    def pegar_token():
        """
        Obtém o token de acesso (Bearer Token) via OAuth2.
        
        Utiliza as credenciais CLIENT_ID e CLIENT_SECRET configuradas no .env.
        """
        client_id = config("NUVEM_CLIENT_ID")
        client_secret = config("NUVEM_CLIENT_SECRET")
        url = "https://auth.nuvemfiscal.com.br/oauth/token"

        # Preparação das credenciais em Base64 para autenticação Basic
        credenciais = f"{client_id}:{client_secret}"
        credenciais_b64 = base64.b64encode(credenciais.encode()).decode()

        headers = {
            "Authorization": f"Basic {credenciais_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            resp = requests.post(
                url,
                headers=headers,
                data={"grant_type": "client_credentials", "scope": "nfce"},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json()["access_token"]
            else:
                raise Exception(f"Erro Auth: {resp.text}")
        except Exception as e:
            raise Exception(f"Falha na autenticação: {str(e)}")

    @staticmethod
    def emitir_nfce(itens_carrinho, forma_pagamento="01"):
        """
        Monta o XML/JSON da NFC-e e envia para autorização.
        
        Args:
            itens_carrinho (list): Lista de dicionários com dados dos produtos.
            forma_pagamento (str): Código da forma de pagamento (ex: '01' para dinheiro).
            
        Returns:
            tuple: (sucesso: bool, dados_ou_erro: dict/str, valor_total: float)
        """
        try:
            token = NuvemFiscalService.pegar_token()

            # --- 1. Dados do Emitente (Carregados do Ambiente) ---
            try:
                crt_valor = int(config("EMPRESA_CRT", default="1"))
            except:
                crt_valor = 1

            emitente_data = {
                "CNPJ": config("CNPJ_EMITENTE"),
                "xNome": config("EMPRESA_NOME", default="Minha Empresa"),
                "enderEmit": {
                    "xLgr": config("EMPRESA_LOGRADOURO", default="Rua Principal"),
                    "nro": config("EMPRESA_NUMERO", default="100"),
                    "xBairro": config("EMPRESA_BAIRRO", default="Centro"),
                    "cMun": config("EMPRESA_COD_MUNICIPIO", default="2111300"),
                    "xMun": config("EMPRESA_MUNICIPIO", default="Cidade"),
                    "UF": config("EMPRESA_UF", default="MA"),
                    "CEP": config("EMPRESA_CEP", default="65000000"),
                    "cPais": "1058",
                    "xPais": "BRASIL",
                },
                "IE": config("IE_EMITENTE"),
                "CRT": crt_valor,
            }

            # --- 2. Processamento dos Itens do Carrinho ---
            detalhes = []
            valor_total_nota = 0.0

            for i, item in enumerate(itens_carrinho):
                total_item = float(item["valor_total"])
                preco_unit = float(item["preco_unitario"])

                detalhe = {
                    "nItem": i + 1,
                    "prod": {
                        "cProd": str(item["id"]),
                        "cEAN": "SEM GTIN",
                        "xProd": item["nome"],
                        "NCM": item.get("ncm", "00000000"),
                        "CFOP": "5102",
                        "uCom": "UN",
                        "qCom": float(item["quantidade"]),
                        "vUnCom": preco_unit,
                        "vProd": total_item,
                        "cEANTrib": "SEM GTIN",
                        "uTrib": "UN",
                        "qTrib": float(item["quantidade"]),
                        "vUnTrib": preco_unit,
                        "indTot": 1,
                    },
                    "imposto": {
                        "ICMS": {"ICMSSN102": {"orig": 0, "CSOSN": "102"}},
                        "PIS": {"PISNT": {"CST": "07"}},
                        "COFINS": {"COFINSNT": {"CST": "07"}},
                    },
                }
                detalhes.append(detalhe)
                valor_total_nota += total_item
                
            # --- 3. Configuração do Pagamento ---
            det_pag = {
                "tPag": forma_pagamento, 
                "vPag": round(valor_total_nota, 2)
            }
            
            if forma_pagamento in ["03", "04", "17"]: # Cartões ou PIX
                det_pag["card"] = {"tpIntegra": 2}

            # --- 4. Numeração e Identificação da Nota ---
            data_emissao = datetime.now().astimezone().isoformat()
            ultima_nota = NotaFiscal.objects.order_by("-numero").first()
            numero_nota = (ultima_nota.numero + 1) if ultima_nota else 1

            # --- 5. Montagem do Payload Final ---
            payload = {
                "ambiente": "homologacao", # Mudar para 'producao' no futuro
                "infNFe": {
                    "versao": "4.00",
                    "ide": {
                        "cUF": 21, # Maranhão
                        "natOp": "VENDA",
                        "mod": 65, # NFC-e
                        "serie": 2,
                        "nNF": numero_nota,
                        "dhEmi": data_emissao,
                        "tpNF": 1,
                        "idDest": 1,
                        "cMunFG": config("EMPRESA_COD_MUNICIPIO", default="2111300"),
                        "tpImp": 4, # DANFE NFC-e
                        "tpEmis": 1,
                        "tpAmb": 2, # 2=Homologação
                        "finNFe": 1,
                        "indFinal": 1,
                        "indPres": 1,
                        "procEmi": 0,
                        "verProc": "1.0",
                    },
                    "emit": emitente_data,
                    "det": detalhes,
                    "total": {
                        "ICMSTot": {
                            "vBC": 0.00, "vICMS": 0.00, "vICMSDeson": 0.00,
                            "vFCP": 0.00, "vBCST": 0.00, "vST": 0.00,
                            "vFCPST": 0.00, "vFCPSTRet": 0.00, "vProd": valor_total_nota,
                            "vFrete": 0.00, "vSeg": 0.00, "vDesc": 0.00,
                            "vII": 0.00, "vIPI": 0.00, "vIPIDevol": 0.00,
                            "vPIS": 0.00, "vCOFINS": 0.00, "vOutro": 0.00,
                            "vNF": valor_total_nota,
                        }
                    },
                    "transp": {"modFrete": 9},
                    "pag": {"detPag": [det_pag] },
                },
            }

            # --- 6. Envio para a API ---
            url = "https://api.sandbox.nuvemfiscal.com.br/nfce"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=30)

            try:
                resp_data = resp.json()
            except:
                return False, f"Erro Crítico ({resp.status_code}): {resp.text}", 0.0

            # --- 7. Tratamento do Retorno ---
            if resp_data.get("status") == "rejeitado":
                motivo = resp_data.get("autorizacao", {}).get(
                    "motivo_status", "Motivo desconhecido"
                )
                return False, f"REJEIÇÃO: {motivo}", 0.0

            if resp.status_code in [200, 201]:
                return True, resp_data, valor_total_nota
            else:
                return False, str(resp_data), 0.0

        except Exception as e:
            return False, f"Erro Interno: {str(e)}", 0.0

    @staticmethod
    def baixar_pdf(id_nota_nuvem):
        """
        Busca o binário do PDF na API da Nuvem Fiscal.
        """
        try:
            token = NuvemFiscalService.pegar_token()
            url = f"https://api.sandbox.nuvemfiscal.com.br/nfce/{id_nota_nuvem}/pdf"
            headers = {"Authorization": f"Bearer {token}"}

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.content, None
            else:
                erro_msg = f"Erro API ({response.status_code}): {response.text}"
                return None, erro_msg
        except Exception as e:
            return None, f"Erro interno ao baixar: {str(e)}"