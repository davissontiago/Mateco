import requests
import base64
import json
from datetime import datetime
from .models import NotaFiscal


class NuvemFiscalService:
    """
    Serviço responsável pela comunicação com a API da Nuvem Fiscal.

    Agora 100% compatível com o sistema Multi-Empresa (Multi-Tenant).
    Recebe o objeto 'empresa' como parâmetro para usar as credenciais corretas.
    """
    
    AUTH_URL = "https://auth.nuvemfiscal.com.br/oauth/token"
    
    @classmethod
    def get_base_url(cls, empresa):
        """
        Retorna a URL correta da API dependendo do ambiente da empresa.
        """
        if empresa.ambiente == 'producao':
            return "https://api.nuvemfiscal.com.br/nfe/v2"
        else:
            return "https://api.sandbox.nuvemfiscal.com.br/nfe/v2"

    @classmethod
    def pegar_token(cls, empresa):
        """
        Obtém o token de acesso (Bearer Token) via OAuth2.

        Utiliza as credenciais CLIENT_ID e CLIENT_SECRET vindas do objeto EMPRESA
        do banco de dados, e não mais do arquivo .env.
        """
        
        # 1. Seleciona as chaves baseadas no "Interruptor" do banco
        if empresa.ambiente == 'producao':
            client_id = empresa.nuvem_client_id_producao
            client_secret = empresa.nuvem_client_secret_producao
            scope = "cnpj" 
        else:
            client_id = empresa.nuvem_client_id_homologacao
            client_secret = empresa.nuvem_client_secret_homologacao
            scope = "cnpj"
            
        # 2. Validação básica
        if not client_id or not client_secret:
            print(f"ERRO: Credenciais não preenchidas para o ambiente: {empresa.get_ambiente_display()}")
            return None
        
        # 3. Requisição do Token
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope
        }
        
        try:
            response = requests.post(cls.AUTH_URL, data=payload, timeout=10)
            if response.status_code == 200:
                return response.json().get("access_token")
            else:
                print(f"Erro Auth Nuvem Fiscal: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Erro de conexão na Auth: {e}")
            return None

    @classmethod
    def emitir_nfce(cls, empresa, itens_carrinho, forma_pagamento="01", cliente=None):
        """
        Monta o XML/JSON da NFC-e e envia para autorização.
        """
        try:
            # --- CONFIGURAÇÃO DO AMBIENTE (INTERRUPTOR) ---
            is_producao = (empresa.ambiente == 'producao')
            
            # Definições dinâmicas
            env_str = "producao" if is_producao else "homologacao"
            tp_amb_code = 1 if is_producao else 2  
            serie_nota = 2 if is_producao else 1 # Quero 2 para produção e 1 para testes
            
            # Seleciona a URL correta
            base_url = cls.get_base_url(empresa)
            
            print(f"--- INICIANDO EMISSÃO EM: {env_str.upper()} ---")
            
            # 1. Autenticação
            token = cls.pegar_token(empresa)
            if not token:
                return False, "Falha na autenticação", 0.0

            # 2. Dados do Emitente
            cod_municipio = empresa.cod_municipio
            
            emitente_data = {
                "CNPJ": empresa.cnpj,
                "xNome": empresa.nome,
                "enderEmit": {
                    "xLgr": empresa.logradouro,
                    "nro": empresa.numero,
                    "xBairro": empresa.bairro,
                    "cMun": cod_municipio,
                    "xMun": empresa.cidade,
                    "UF": empresa.uf,
                    "CEP": empresa.cep,
                    "cPais": "1058",
                    "xPais": "BRASIL",
                },
                "IE": empresa.inscricao_estadual,
                "CRT": int(empresa.crt),
            }

            # 3. Processamento do Destinatário
            dest_data = None
            if cliente:
                doc_limpo = cliente.cpf_cnpj.replace(".", "").replace("-", "").replace("/", "")
                
                dest_data = {
                    "xNome": cliente.nome,
                    "indIEDest": 9, 
                }

                if len(doc_limpo) == 11:
                    dest_data["CPF"] = doc_limpo
                else:
                    dest_data["CNPJ"] = doc_limpo

                if cliente.endereco:
                    dest_data["enderDest"] = {
                        "xLgr": cliente.endereco,
                        "nro": cliente.numero or "S/N",
                        "xBairro": cliente.bairro or "Centro",
                        "cMun": cod_municipio,
                        "xMun": cliente.cidade,
                        "UF": cliente.uf,
                        "CEP": cliente.cep or "65630000",
                        "cPais": "1058",
                        "xPais": "BRASIL"
                    }

            # 4. Itens
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

            # 5. Pagamento
            det_pag = {"tPag": forma_pagamento, "vPag": round(valor_total_nota, 2)}
            if forma_pagamento in ["03", "04", "17"]:
                det_pag["card"] = {"tpIntegra": 2}

            # 6. Numeração e Identificação
            data_emissao = datetime.now().astimezone().isoformat()
            
            # Busca a última nota da SÉRIE correta
            ultima_nota = NotaFiscal.objects.filter(empresa=empresa).order_by("-numero").first()
            numero_nota = (ultima_nota.numero + 1) if ultima_nota else 1

            payload = {
                "ambiente": env_str,
                "infNFe": {
                    "versao": "4.00",
                    "ide": {
                        "cUF": 21,
                        "natOp": "VENDA",
                        "mod": 65,
                        "serie": serie_nota,
                        "nNF": numero_nota,
                        "dhEmi": data_emissao,
                        "tpNF": 1,
                        "idDest": 1,
                        "cMunFG": cod_municipio,
                        "tpImp": 4,
                        "tpEmis": 1,
                        "tpAmb": tp_amb_code,
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
                    "pag": {"detPag": [det_pag]},
                },
            }

            # Insere o destinatário se existir
            if dest_data:
                payload["infNFe"]["dest"] = dest_data

            # 7. Envio
            url = f"{base_url}/nfce"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=30)

            try:
                resp_data = resp.json()
            except:
                return False, f"Erro Crítico ({resp.status_code}): {resp.text}", 0.0

            if resp_data.get("status") == "rejeitado":
                motivo = resp_data.get("autorizacao", {}).get("motivo_status", "Motivo desconhecido")
                return False, f"REJEIÇÃO: {motivo}", 0.0

            if resp.status_code in [200, 201]:
                return True, resp_data, valor_total_nota
            else:
                return False, str(resp_data), 0.0

        except Exception as e:
            return False, f"Erro Interno no Serviço: {str(e)}", 0.0

    @classmethod
    def baixar_pdf(cls, empresa, id_nota_nuvem):
        """
        Busca o binário do PDF na API da Nuvem Fiscal.
        Precisa do token da empresa que emitiu a nota.
        """
        try:
            token = cls.pegar_token(empresa)
            if not token:
                return None, "Falha na autenticação (Token)"

            base_url = cls.get_base_url(empresa)
            url = f"{base_url}/nfce/{id_nota_nuvem}/pdf"
            headers = {"Authorization": f"Bearer {token}"}

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.content, None
            else:
                erro_msg = f"Erro API ({response.status_code}): {response.text}"
                return None, erro_msg
        except Exception as e:
            return None, f"Erro interno ao baixar: {str(e)}"
