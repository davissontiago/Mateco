"""
Roteador fiscal: despacha emissão e cancelamento para o emissor configurado
na Empresa (empresa.emissor_fiscal).

- 'direto' → core.sefaz_service.SefazService (comunicação direta com SEFAZ)
- 'nuvem'  → core.services.NuvemFiscalService (API NuvemFiscal)
"""


class FiscalRouter:
    @staticmethod
    def _is_direto(empresa) -> bool:
        return getattr(empresa, "emissor_fiscal", "nuvem") == "direto"

    @classmethod
    def emitir_nfce(cls, empresa, itens_carrinho, pagamentos, troco=0.0, cliente=None, desconto_global=0.0):
        if cls._is_direto(empresa):
            from core.sefaz_service import SefazService
            return SefazService.emitir_nfce(empresa, itens_carrinho, pagamentos, troco, cliente, desconto_global)
        from core.services import NuvemFiscalService
        # NuvemFiscalService usa forma_pagamento como string; extrai do primeiro pagamento
        forma_pagamento = pagamentos[0]['forma_pagamento'] if pagamentos else '01'
        return NuvemFiscalService.emitir_nfce(
            empresa=empresa,
            itens_carrinho=itens_carrinho,
            forma_pagamento=forma_pagamento,
            cliente=cliente,
        )

    @classmethod
    def cancelar_nfce(cls, empresa, nota_fiscal, justificativa):
        if cls._is_direto(empresa):
            from core.sefaz_service import SefazService
            return SefazService.cancelar_nfce(empresa, nota_fiscal, justificativa)
        from core.services import NuvemFiscalService
        return NuvemFiscalService.cancelar_nfce(
            empresa=empresa,
            id_nota=nota_fiscal.id_nota,
            justificativa=justificativa,
        )

    @classmethod
    def consultar_nfce_por_chave(cls, empresa, chave):
        if cls._is_direto(empresa):
            from core.sefaz_service import SefazService
            return SefazService.consultar_nfce_por_chave(empresa, chave)
        consultar = getattr(__import__("core.services", fromlist=["NuvemFiscalService"]).NuvemFiscalService, "consultar_nfce_por_chave", None)
        if consultar is None:
            return None
        return consultar(empresa, chave)
