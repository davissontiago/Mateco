import requests
import json
from datetime import datetime
from .models import NotaFiscal

class NuvemFiscalService:
    """
    Serviço central responsável por toda a comunicação com a API da Nuvem Fiscal.
    
    Funcionalidades:
    1. Autenticação (OAuth2)
    2. Emissão de NFC-e (Nota Fiscal de Consumidor)
    3. Download de PDF (DANFE)
    4. Consulta de Status (Recuperação de falhas)

    Compatibilidade:
    - Suporta Múltiplas Empresas (Multi-Tenant).
    - Alterna automaticamente entre Produção e Homologação (Sandbox).
    """
    
    # Endpoint fixo para obter o Token de Acesso
    AUTH_URL = "https://auth.nuvemfiscal.com.br/oauth/token"

    @classmethod
    def get_base_url(cls, empresa):
        """
        Define a URL raiz da API com base no ambiente configurado na empresa.
        
        Args:
            empresa (Empresa): Objeto do banco contendo a configuração 'ambiente'.
            
        Returns:
            str: URL base (sem o endpoint específico).
        """
        if empresa.ambiente == 'producao':
            return "https://api.nuvemfiscal.com.br"
        else:
            return "https://api.sandbox.nuvemfiscal.com.br"

    @classmethod
    def pegar_token(cls, empresa):
        """
        Realiza a autenticação OAuth2 (Client Credentials).
        
        O Token gerado tem validade temporária (geralmente 1 hora) e permite
        que o sistema realize ações em nome da empresa.
        
        OBS: O escopo 'nfce cnpj' é obrigatório para emitir notas.
        """
        
        # 1. Seleciona as chaves corretas baseadas no ambiente
        if empresa.ambiente == 'producao':
            client_id = empresa.nuvem_client_id_producao
            client_secret = empresa.nuvem_client_secret_producao
        else:
            client_id = empresa.nuvem_client_id_homologacao
            client_secret = empresa.nuvem_client_secret_homologacao
            
        # 2. Validação básica de segurança
        if not client_id or not client_secret:
            print(f"ERRO CRÍTICO: Sem credenciais configuradas para {empresa.nome} no ambiente {empresa.ambiente}")
            return None
        
        # 3. Payload de Autenticação
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "nfce cnpj" # 'nfce' permite emitir, 'cnpj' permite consultar dados
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
        Orquestra todo o processo de emissão da NFC-e.
        
        Passos:
        1. Autentica e pega o Token.
        2. Calcula a numeração sequencial (baseado na última nota do banco).
        3. Monta o JSON complexo exigido pela SEFAZ.
        4. Envia para a API.
        5. Valida a resposta com rigor para evitar 'falsos positivos'.
        
        Returns:
            Tuple: (Sucesso: bool, Dados/Erro: dict/str, ValorTotal: float)
        """
        try:
            # --- CONFIGURAÇÃO DO AMBIENTE ---
            is_producao = (empresa.ambiente == 'producao')
            
            # Strings e Códigos exigidos pela SEFAZ
            env_str = "producao" if is_producao else "homologacao"
            tp_amb_code = 1 if is_producao else 2  
            
            # Separação de Séries: Série 1 para Testes, Série 2 para Produção
            serie_nota = 2 if is_producao else 1 
            
            base_url = cls.get_base_url(empresa)
            
            print(f"--- INICIANDO EMISSÃO EM: {env_str.upper()} (Série {serie_nota}) ---")
            
            # 1. Autenticação
            token = cls.pegar_token(empresa)
            if not token:
                return False, "Falha na autenticação (Verifique as Credenciais)", 0.0

            # 2. Dados do Emitente (Quem está vendendo)
            emitente_data = {
                "CNPJ": empresa.cnpj,
                "xNome": empresa.nome,
                "enderEmit": {
                    "xLgr": empresa.logradouro,
                    "nro": empresa.numero,
                    "xBairro": empresa.bairro,
                    "cMun": empresa.cod_municipio,
                    "xMun": empresa.cidade,
                    "UF": empresa.uf,
                    "CEP": empresa.cep,
                    "cPais": "1058",
                    "xPais": "BRASIL",
                },
                "IE": empresa.inscricao_estadual,
                "CRT": int(empresa.crt), # 1=Simples Nacional, 3=Regime Normal
            }

            # 3. Dados do Destinatário (Opcional na NFC-e, mas obrigatório se > R$ 10k)
            dest_data = None
            if cliente:
                # Remove pontuação para evitar erro de validação
                doc_limpo = cliente.cpf_cnpj.replace(".", "").replace("-", "").replace("/", "")
                
                dest_data = {
                    "xNome": cliente.nome,
                    "indIEDest": 9, # 9 = Não Contribuinte
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
                        "cMun": empresa.cod_municipio,
                        "xMun": cliente.cidade,
                        "UF": cliente.uf,
                        "CEP": cliente.cep or "65000000",
                        "cPais": "1058",
                        "xPais": "BRASIL"
                    }

            # 4. Processamento dos Itens do Carrinho
            detalhes = []
            valor_total_nota = 0.0

            for i, item in enumerate(itens_carrinho):
                total_item = float(item["valor_total"])
                preco_unit = float(item["preco_unitario"])

                detalhe = {
                    "nItem": i + 1,
                    "prod": {
                        "cProd": str(item["id"]),
                        "cEAN": "SEM GTIN", # Ou o código de barras real se tiver
                        "xProd": item["nome"],
                        "NCM": item.get("ncm", "00000000"), # NCM Genérico se não tiver
                        "CFOP": "5102", # Venda de mercadoria
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
                        # Configuração simplificada para Simples Nacional (CSOSN 102)
                        "ICMS": {"ICMSSN102": {"orig": 0, "CSOSN": "102"}},
                        "PIS": {"PISNT": {"CST": "07"}},
                        "COFINS": {"COFINSNT": {"CST": "07"}},
                    },
                }
                detalhes.append(detalhe)
                valor_total_nota += total_item

            # 5. Formas de Pagamento
            det_pag = {"tPag": forma_pagamento, "vPag": round(valor_total_nota, 2)}
            
            # Se for Cartão (03/04), a SEFAZ pede informações da maquininha (independente se integrado ou não)
            # tpIntegra: 2 = Não integrado (maquininha separada)
            if forma_pagamento in ["03", "04", "17"]:
                det_pag["card"] = {"tpIntegra": 2}

            # 6. Numeração Sequencial
            # Busca a última nota emitida por ESTA empresa nesta SÉRIE específica
            ultima = NotaFiscal.objects.filter(
                empresa=empresa, 
                serie=serie_nota
            ).order_by("-numero").first()
            
            numero_nota = (ultima.numero + 1) if ultima else 1
            
            # 7. Montagem do Payload Final (JSON)
            payload = {
                "ambiente": env_str, # "homologacao" ou "producao"
                "infNFe": {
                    "versao": "4.00",
                    "ide": {
                        "cUF": 21, # Código do MA (Maranhão)
                        "natOp": "VENDA",
                        "mod": 65, # 65 = NFC-e / 55 = NF-e
                        "serie": serie_nota,
                        "nNF": numero_nota,
                        "dhEmi": datetime.now().astimezone().isoformat(),
                        "tpNF": 1, # 1 = Saída
                        "idDest": 1, # 1 = Operação interna
                        "cMunFG": empresa.cod_municipio,
                        "tpImp": 4, # 4 = DANFE NFC-e
                        "tpEmis": 1, # 1 = Normal
                        "tpAmb": tp_amb_code,
                        "finNFe": 1, # 1 = Normal
                        "indFinal": 1, # 1 = Consumidor Final
                        "indPres": 1, # 1 = Presencial
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
                    "transp": {"modFrete": 9}, # 9 = Sem frete
                    "pag": {"detPag": [det_pag]},
                },
            }

            if dest_data:
                payload["infNFe"]["dest"] = dest_data

            # 8. Envio para API
            url = f"{base_url}/nfce"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            
            resp = requests.post(url, json=payload, headers=headers, timeout=30)

            try:
                resp_data = resp.json()
            except:
                return False, f"Erro Crítico de Comunicação ({resp.status_code}): {resp.text}", 0.0
            
            # --- VALIDAÇÃO DE SEGURANÇA E STATUS ---
            
            # Caso 1: Rejeição Explícita da SEFAZ (ex: NCM inválido, CNPJ errado)
            if resp_data.get("status") == "rejeitado":
                motivo = resp_data.get("autorizacao", {}).get("motivo_status", "Motivo desconhecido")
                msg_detalhe = resp_data.get("mensagem", "")
                return False, f"REJEIÇÃO SEFAZ: {motivo} {msg_detalhe}", 0.0
            
            # Caso 2: Resposta HTTP Sucesso (200/201) - Validamos o status interno
            if resp.status_code in [200, 201]:
                status_nota = resp_data.get("status", "").lower()
                
                if status_nota == "autorizado":
                    # SUCESSO REAL: Só retorna True aqui!
                    return True, resp_data, valor_total_nota
                
                elif status_nota == "denegado":
                    return False, "NOTA DENEGADA: Irregularidade fiscal do emitente ou destinatário.", 0.0
                
                elif status_nota == "processando":
                    return False, "A SEFAZ está lenta e processando. Consulte em instantes.", 0.0
                
                else:
                    return False, f"Status inesperado da nota: {status_nota}", 0.0
            
            # Caso 3: Erro de Validação de Dados da API (Campos obrigatórios faltando)
            else:
                error_obj = resp_data.get("error", {})
                msg = error_obj.get("message")

                # Tenta extrair mensagem amigável da lista de erros
                if not msg and "errors" in error_obj:
                    primeiro_erro = error_obj["errors"][0] 
                    msg = f"{primeiro_erro.get('message')} (Campo: {primeiro_erro.get('path')})"
                
                if not msg:
                    msg = "Erro desconhecido na API."

                return False, f"Erro de Validação: {msg}", 0.0

        except Exception as e:
            return False, f"Erro Interno no Serviço: {str(e)}", 0.0

    @classmethod
    def baixar_pdf(cls, empresa, id_nota_nuvem):
        """
        Recupera o binário do PDF (DANFE) da API.
        
        Args:
            id_nota_nuvem: O ID único gerado pela Nuvem Fiscal (ex: 'nfe_12345...')
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
        
    @classmethod
    def consultar_nota_por_numero(cls, empresa, numero, serie):
        """
        Rede de Segurança: Consulta se uma nota existe na Nuvem Fiscal.
        Útil para casos de Timeout (Internet caiu durante a emissão).
        
        Args:
            numero (int): Número da nota (nNF)
            serie (int): Série da nota
            
        Returns:
            Tuple: (Encontrada: bool/None, Dados: dict/str)
        """
        try:
            token = cls.pegar_token(empresa)
            if not token: return False, "Falha Autenticação"

            base_url = cls.get_base_url(empresa)
            url = f"{base_url}/nfce"
            
            # Prepara os filtros obrigatórios para a busca
            cnpj_limpo = empresa.cnpj.replace('.', '').replace('/', '').replace('-', '')
            env_str = "producao" if empresa.ambiente == 'producao' else "homologacao"

            params = {
                "cpf_cnpj": cnpj_limpo,  # Obrigatório na busca
                "ambiente": env_str,     # Obrigatório na busca
                "numero": numero,
                "serie": serie,
                "count": 1,              # Traz apenas 1 registro
                "orderby": "data_emissao_desc"
            }

            resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                lista_notas = data.get("data", [])
                
                if not lista_notas:
                    return None, "Nota não encontrada"
                
                # Retorna os dados da primeira nota encontrada
                return True, lista_notas[0]
            
            return False, f"Erro na Consulta: {resp.text}"

        except Exception as e:
            return False, f"Erro Interno: {str(e)}"