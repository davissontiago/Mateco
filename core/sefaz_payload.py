"""
Construção do payload NFC-e como objeto tipado (nfelib.Nfe).

Função pura, sem efeitos colaterais e sem I/O. Recebe dados já resolvidos
pela view (empresa, carrinho, pagamentos, numeração) e devolve um Nfe pronto
para ser assinado/transmitido pelo SefazService.

Adaptado de matech-backend/fiscal/sefaz_payload.py para o modelo Empresa do
NotasAuto (usa `nome` como razão social e `cidade` como município).
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from erpbrasil.base.fiscal.edoc import ChaveEdoc
from nfelib.nfe.bindings.v4_0.leiaute_nfe_v4_00 import (
    CardTpIntegra,
    CofinsntCst,
    DetPagIndPag,
    EmitCrt,
    Icmssn102Csosn,
    IdeIdDest,
    IdeIndFinal,
    IdeIndPres,
    IdeTpEmis,
    IdeTpImp,
    IdeTpNf,
    PisntCst,
    ProdIndTot,
    Tamb,
    TcodUfIbge,
    TenderEmi,
    Tendereco,
    TfinNfe,
    Tmod,
    Tnfe,
    Torig,
    TprocEmi,
    Tuf,
)
from nfelib.nfe.bindings.v4_0.nfe_v4_00 import Nfe


UF_CODIGO_IBGE = {
    "AC": 12, "AL": 27, "AM": 13, "AP": 16, "BA": 29, "CE": 23,
    "DF": 53, "ES": 32, "GO": 52, "MA": 21, "MG": 31, "MS": 50,
    "MT": 51, "PA": 15, "PB": 25, "PE": 26, "PI": 22, "PR": 41,
    "RJ": 33, "RN": 24, "RO": 11, "RR": 14, "RS": 43, "SC": 42,
    "SE": 28, "SP": 35, "TO": 17,
}


def _fmt2(v) -> str:
    return str(Decimal(str(float(v))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _fmt4(v) -> str:
    return str(Decimal(str(float(v))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _ender_emit(empresa) -> TenderEmi:
    return TenderEmi(
        xLgr=empresa.logradouro,
        nro=empresa.numero or "S/N",
        xBairro=empresa.bairro,
        cMun=str(empresa.cod_municipio),
        xMun=empresa.cidade,          # NotasAuto: campo `cidade`
        UF=Tuf(empresa.uf.upper()),
        CEP=_only_digits(empresa.cep),
        cPais="1058",
        xPais="BRASIL",
    )


def _ender_dest(cliente, empresa) -> Tendereco | None:
    endereco = getattr(cliente, "endereco", None)
    if not endereco:
        return None
    return Tendereco(
        xLgr=endereco,
        nro=getattr(cliente, "numero", "") or "S/N",
        xBairro=getattr(cliente, "bairro", "") or "Centro",
        cMun=str(getattr(cliente, "cod_municipio", "") or empresa.cod_municipio),
        xMun=getattr(cliente, "cidade", "") or empresa.cidade,
        UF=Tuf((getattr(cliente, "uf", "") or empresa.uf).upper()),
        CEP=_only_digits(getattr(cliente, "cep", "") or empresa.cep),
        cPais="1058",
        xPais="BRASIL",
    )


def _dest(cliente, empresa) -> Tnfe.InfNfe.Dest | None:
    if cliente is None or not getattr(cliente, "cpf_cnpj", None):
        return None
    doc = _only_digits(cliente.cpf_cnpj)
    kwargs = {
        "xNome": cliente.nome,
        "indIEDest": Tnfe.InfNfe.Dest.IndIeDest.VALUE_9
        if hasattr(Tnfe.InfNfe.Dest, "IndIeDest")
        else "9",
    }
    if len(doc) == 11:
        kwargs["CPF"] = doc
    else:
        kwargs["CNPJ"] = doc
    ender = _ender_dest(cliente, empresa)
    if ender is not None:
        kwargs["enderDest"] = ender
    return Tnfe.InfNfe.Dest(**kwargs)


def _imposto_simples_nacional() -> Tnfe.InfNfe.Det.Imposto:
    Imposto = Tnfe.InfNfe.Det.Imposto
    return Imposto(
        ICMS=Imposto.Icms(
            ICMSSN102=Imposto.Icms.Icmssn102(
                orig=Torig.VALUE_0,
                CSOSN=Icmssn102Csosn.VALUE_102,
            )
        ),
        PIS=Imposto.Pis(PISNT=Imposto.Pis.Pisnt(CST=PisntCst.VALUE_07)),
        COFINS=Imposto.Cofins(COFINSNT=Imposto.Cofins.Cofinsnt(CST=CofinsntCst.VALUE_07)),
    )


_XPROD_HOMOLOGACAO = "NOTA FISCAL EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"


def _det(item: dict, indice: int, is_homologacao: bool = False, vdesc: str = "0.00") -> Tnfe.InfNfe.Det:
    unidade = item.get("unidade_medida", "UN")
    xprod = _XPROD_HOMOLOGACAO if (is_homologacao and indice == 1) else item["nome"]

    q_str = _fmt4(item["quantidade"])
    v_str = _fmt2(item["preco_unitario"])
    # vProd deve ser exatamente qCom × vUnCom para passar a validação SEFAZ 562
    v_prod = str(
        (Decimal(q_str) * Decimal(v_str)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    kwargs = dict(
        cProd=str(item["id"]),
        cEAN="SEM GTIN",
        xProd=xprod,
        NCM=(item.get("ncm") or "00000000"),
        CFOP=str(item.get("cfop") or "5102"),
        uCom=unidade,
        qCom=q_str,
        vUnCom=v_str,
        vProd=v_prod,
        cEANTrib="SEM GTIN",
        uTrib=unidade,
        qTrib=q_str,
        vUnTrib=v_str,
        indTot=ProdIndTot.VALUE_1,
    )
    if Decimal(vdesc) > 0:
        kwargs["vDesc"] = vdesc

    prod = Tnfe.InfNfe.Det.Prod(**kwargs)
    det = Tnfe.InfNfe.Det(prod=prod, imposto=_imposto_simples_nacional())
    det.nItem = str(indice)
    return det


_TPAG_CARTAO = {"03", "04", "17"}


def _det_pag(pag: dict) -> Tnfe.InfNfe.Pag.DetPag:
    forma = str(pag.get("forma_pagamento", "")).strip().zfill(2)
    valor = float(pag.get("valor", 0) or 0)
    card = None
    if forma in _TPAG_CARTAO:
        card = Tnfe.InfNfe.Pag.DetPag.Card(
            tpIntegra=CardTpIntegra.VALUE_2,
            tBand="99",
            cAut="000000",
        )
    return Tnfe.InfNfe.Pag.DetPag(
        indPag=DetPagIndPag.VALUE_0,
        tPag=forma,
        vPag=_fmt2(valor),
        card=card,
    )


def _total(valor_prod: float, desconto: float = 0.0) -> Tnfe.InfNfe.Total:
    zero = _fmt2(0)
    vprod = _fmt2(valor_prod)
    vdesc = _fmt2(desconto) if desconto > 0.005 else zero
    vnf = str(
        (Decimal(vprod) - Decimal(vdesc)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    return Tnfe.InfNfe.Total(
        ICMSTot=Tnfe.InfNfe.Total.Icmstot(
            vBC=zero, vICMS=zero, vICMSDeson=zero, vFCP=zero,
            vBCST=zero, vST=zero, vFCPST=zero, vFCPSTRet=zero,
            vProd=vprod, vFrete=zero, vSeg=zero, vDesc=vdesc,
            vII=zero, vIPI=zero, vIPIDevol=zero, vPIS=zero,
            vCOFINS=zero, vOutro=zero, vNF=vnf,
        )
    )


def montar_nfce(
    empresa,
    itens_carrinho: list,
    pagamentos: list,
    cliente=None,
    numero: int = 1,
    serie: int = 1,
    desconto_global: float = 0.0,
) -> Nfe:
    """
    Monta o objeto NFC-e (Nfe) pronto para assinatura/transmissão.

    Parâmetros:
        empresa: instância de core.models.Empresa
        itens_carrinho: lista de dicts com id, nome, quantidade,
            preco_unitario, valor_total, ncm, cfop, unidade_medida
        pagamentos: lista de dicts com forma_pagamento e valor
        cliente: instância de core.models.Cliente (opcional)
        numero: nNF sequencial por série
        serie: número da série NFC-e

    Retorna:
        Nfe com infNFe.Id = f"NFe{chave44}" já calculado.
    """
    uf_sigla = (empresa.uf or "").upper()
    uf_codigo = UF_CODIGO_IBGE.get(uf_sigla)
    if uf_codigo is None:
        raise ValueError(f"UF '{uf_sigla}' não mapeada para código IBGE.")

    cnpj = _only_digits(empresa.cnpj)
    agora = datetime.now().astimezone()
    ano_mes = agora.strftime("%y%m")

    chave = ChaveEdoc(
        codigo_uf=uf_codigo,
        ano_mes=ano_mes,
        cnpj_cpf_emitente=cnpj,
        modelo_documento="65",
        numero_serie=str(serie),
        numero_documento=str(numero),
        forma_emissao="1",
    )
    chave44 = chave.chave
    c_nf = chave44[35:43]
    c_dv = chave44[43]

    is_producao = empresa.ambiente == "producao"
    tp_amb = Tamb.VALUE_1 if is_producao else Tamb.VALUE_2

    ide = Tnfe.InfNfe.Ide(
        cUF=TcodUfIbge(str(uf_codigo)),
        cNF=c_nf,
        natOp="VENDA",
        mod=Tmod.VALUE_65,
        serie=str(serie),
        nNF=str(numero),
        dhEmi=agora.isoformat(timespec="seconds"),
        tpNF=IdeTpNf.VALUE_1,
        idDest=IdeIdDest.VALUE_1,
        cMunFG=str(empresa.cod_municipio),
        tpImp=IdeTpImp.VALUE_4,
        tpEmis=IdeTpEmis.VALUE_1,
        cDV=c_dv,
        tpAmb=tp_amb,
        finNFe=TfinNfe.VALUE_1,
        indFinal=IdeIndFinal.VALUE_1,
        indPres=IdeIndPres.VALUE_1,
        procEmi=TprocEmi.VALUE_0,
        verProc="NOTASAUTO-1.0",
    )

    emit = Tnfe.InfNfe.Emit(
        CNPJ=cnpj,
        xNome=empresa.nome,                                          # NotasAuto: `nome` = razão social
        xFant=getattr(empresa, "nome_fantasia", None) or empresa.nome,
        enderEmit=_ender_emit(empresa),
        IE=empresa.inscricao_estadual,
        CRT=EmitCrt(str(empresa.crt)) if str(empresa.crt) in {"1", "2", "3", "4"} else EmitCrt.VALUE_1,
    )

    dest = _dest(cliente, empresa)

    is_homologacao = not is_producao
    desconto = Decimal(str(float(desconto_global or 0.0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Primeira passagem: calcula vProd de cada item (qCom × vUnCom)
    v_prods = []
    for item in itens_carrinho:
        q_str = _fmt4(item["quantidade"])
        v_str = _fmt2(item["preco_unitario"])
        v_prod = (Decimal(q_str) * Decimal(v_str)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        v_prods.append(v_prod)

    valor_prod_total = sum(v_prods)

    # Distribui desconto proporcional por item; último item absorve diferença de arredondamento
    v_descs: list[Decimal] = []
    if desconto > 0 and valor_prod_total > 0:
        acumulado = Decimal("0")
        for idx, vp in enumerate(v_prods):
            if idx < len(v_prods) - 1:
                d = (desconto * vp / valor_prod_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                d = desconto - acumulado
            v_descs.append(d)
            acumulado += d
    else:
        v_descs = [Decimal("0")] * len(v_prods)

    dets: list[Tnfe.InfNfe.Det] = []
    for i, (item, vdesc) in enumerate(zip(itens_carrinho, v_descs), start=1):
        det = _det(item, i, is_homologacao=is_homologacao, vdesc=str(vdesc))
        dets.append(det)

    total = _total(float(valor_prod_total), float(sum(v_descs)))

    transp = Tnfe.InfNfe.Transp(modFrete="9")

    detpag_list = [_det_pag(p) for p in pagamentos]
    soma_pag = sum(Decimal(_fmt2(p.get("valor", 0) or 0)) for p in pagamentos)
    v_nf = Decimal(total.ICMSTot.vNF)
    troco_calculado = (soma_pag - v_nf).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    pag_kwargs = {"detPag": detpag_list}
    if troco_calculado > 0:
        pag_kwargs["vTroco"] = str(troco_calculado)
    pag = Tnfe.InfNfe.Pag(**pag_kwargs)

    inf_nfe = Tnfe.InfNfe(
        ide=ide,
        emit=emit,
        dest=dest,
        det=dets,
        total=total,
        transp=transp,
        pag=pag,
        versao="4.00",
        Id=f"NFe{chave44}",
    )

    return Nfe(infNFe=inf_nfe)
