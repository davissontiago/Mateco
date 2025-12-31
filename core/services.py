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

    # URL Base da API (Pode mudar para 'api.nuvemfiscal.com.br' em produção)
    BASE_URL = "https://api.sandbox.nuvemfiscal.com.br"
    AUTH_URL = "https://auth.nuvemfiscal.com.br/oauth/token"

    @classmethod
    def pegar_token(cls, empresa):
        """
        Obtém o token de acesso (Bearer Token) via OAuth2.

        Utiliza as credenciais CLIENT_ID e CLIENT_SECRET vindas do objeto EMPRESA
        do banco de dados, e não mais do arquivo .env.
        """
        # Pega credenciais específicas da Loja/Empresa
        client_id = empresa.nuvem_client_id
        client_secret = empresa.nuvem_client_secret

        # Preparação das credenciais em Base64 para autenticação Basic
        credenciais = f"{client_id}:{client_secret}"
        credenciais_b64 = base64.b64encode(credenciais.encode()).decode()

        headers = {
            "Authorization": f"Basic {credenciais_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            resp = requests.post(
                cls.AUTH_URL,
                headers=headers,
                data={"grant_type": "client_credentials", "scope": "nfce"},
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json()["access_token"]
            else:
                # Log de erro útil para debug
                print(f"Erro Auth NuvemFiscal: {resp.text}")
                return None
        except Exception as e:
            print(f"Falha na conexão Auth: {str(e)}")
            return None

    @classmethod
    def emitir_nfce(
        cls, empresa, itens_carrinho, forma_pagamento="01", cliente=None
    ):  # <--- [NOVO] Adicionado parametro
        """
        Monta o XML/JSON da NFC-e e envia para autorização.
        """
        try:
            # 1. Autenticação usando a empresa correta
            token = cls.pegar_token(empresa)
            if not token:
                return (
                    False,
                    "Falha na autenticação (Verifique Client ID/Secret no cadastro da Empresa)",
                    0.0,
                )

            cod_municipio = (
                "2112209"  # Default Timon (ou adicione 'codigo_ibge' no model Empresa)
            )

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
                "CRT": int(empresa.crt),  # Pega o CRT escolhido no cadastro
            }

            # --- [NOVO] 2. Processamento do Cliente (Destinatário) ---
            dest_data = None
            if cliente:
                # Remove pontuação para evitar erro na SEFAZ
                doc_limpo = (
                    cliente.cpf_cnpj.replace(".", "").replace("-", "").replace("/", "")
                )

                dest_data = {
                    "xNome": cliente.nome,
                    "indIEDest": "9",  # 9 = Não Contribuinte
                }

                if len(doc_limpo) == 11:
                    dest_data["CPF"] = doc_limpo
                else:
                    dest_data["CNPJ"] = doc_limpo

                # Endereço do cliente (Opcional, mas bom ter)
                if cliente.endereco:
                    dest_data["enderDest"] = {
                        "xLgr": cliente.endereco,
                        "nro": cliente.numero or "S/N",
                        "xBairro": cliente.bairro or "Centro",
                        "cMun": cod_municipio,
                        "xMun": cliente.cidade,
                        "UF": cliente.uf,
                        "CEP": cliente.cep or "00000000",
                        "cPais": "1058",
                        "xPais": "BRASIL",
                    }
            # ---------------------------------------------------------

            # --- 3. Processamento dos Itens do Carrinho ---
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

            # --- 4. Configuração do Pagamento ---
            det_pag = {"tPag": forma_pagamento, "vPag": round(valor_total_nota, 2)}

            if forma_pagamento in ["03", "04", "17"]:  # Cartões ou PIX
                det_pag["card"] = {"tpIntegra": 2}

            # --- 5. Numeração e Identificação da Nota ---
            data_emissao = datetime.now().astimezone().isoformat()

            ultima_nota = (
                NotaFiscal.objects.filter(empresa=empresa).order_by("-numero").first()
            )
            numero_nota = (ultima_nota.numero + 1) if ultima_nota else 1

            # --- 6. Montagem do Payload Final ---
            payload = {
                "ambiente": "homologacao",
                "infNFe": {
                    "versao": "4.00",
                    "ide": {
                        "cUF": 21,
                        "natOp": "VENDA",
                        "mod": 65,
                        "serie": 2,
                        "nNF": numero_nota,
                        "dhEmi": data_emissao,
                        "tpNF": 1,
                        "idDest": 1,
                        "cMunFG": cod_municipio,
                        "tpImp": 4,
                        "tpEmis": 1,
                        "tpAmb": 2,
                        "finNFe": 1,
                        "indFinal": 1,
                        "indPres": 1,
                        "procEmi": 0,
                        "verProc": "1.0",
                    },
                    "emit": emitente_data,
                    # "dest": dest_data, (Inserido dinamicamente abaixo)
                    "det": detalhes,
                    "total": {
                        "ICMSTot": {
                            "vBC": 0.00,
                            "vICMS": 0.00,
                            "vICMSDeson": 0.00,
                            "vFCP": 0.00,
                            "vBCST": 0.00,
                            "vST": 0.00,
                            "vFCPST": 0.00,
                            "vFCPSTRet": 0.00,
                            "vProd": valor_total_nota,
                            "vFrete": 0.00,
                            "vSeg": 0.00,
                            "vDesc": 0.00,
                            "vII": 0.00,
                            "vIPI": 0.00,
                            "vIPIDevol": 0.00,
                            "vPIS": 0.00,
                            "vCOFINS": 0.00,
                            "vOutro": 0.00,
                            "vNF": valor_total_nota,
                        }
                    },
                    "transp": {"modFrete": 9},
                    "pag": {"detPag": [det_pag]},
                },
            }

            # --- [NOVO] INSERE O CLIENTE NO PAYLOAD SE EXISTIR ---
            if dest_data:
                payload["infNFe"]["dest"] = dest_data
            # -----------------------------------------------------

            # --- 7. Envio para a API ---
            url = f"{cls.BASE_URL}/nfce"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=30)

            try:
                resp_data = resp.json()
            except:
                return False, f"Erro Crítico ({resp.status_code}): {resp.text}", 0.0

            # --- 8. Tratamento do Retorno ---
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

            url = f"{cls.BASE_URL}/nfce/{id_nota_nuvem}/pdf"
            headers = {"Authorization": f"Bearer {token}"}

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.content, None
            else:
                erro_msg = f"Erro API ({response.status_code}): {response.text}"
                return None, erro_msg
        except Exception as e:
            return None, f"Erro interno ao baixar: {str(e)}"
