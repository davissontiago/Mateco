"""
Geração de DANFE NFC-e (cupom 80 mm) para emissão SEFAZ direto.
Adaptado de matech-backend/fiscal/danfe.py para o modelo do mateco.

Itens e pagamentos são extraídos do xml_assinado da NotaFiscal.
Função principal: gerar_danfe_nfce(nota_fiscal) -> bytes (PDF)
Dependências: reportlab, qrcode[pil]
"""

from io import BytesIO

import qrcode
from lxml import etree
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm as MM
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

# ── dimensões do cupom ────────────────────────────────────────────────────────
_LARGURA  = 80 * MM
_MARGEM_H = 4 * MM
_MARGEM_V = 1 * MM
_W        = _LARGURA - 2 * _MARGEM_H
_IW       = _W - 6

_FRAC     = [7, 20, 9, 7, 14.5, 14.5]
_COL_ITENS = [f / sum(_FRAC) * _IW for f in _FRAC]

# ── estilos ───────────────────────────────────────────────────────────────────
def _s(name, **kw):
    base = dict(fontName="Helvetica", fontSize=7, leading=8,
                textColor=colors.black, wordWrap="LTR")
    base.update(kw)
    return ParagraphStyle(name, **base)

_C   = _s("c",   alignment=1)
_L   = _s("l",   alignment=0)
_R   = _s("r",   alignment=2)
_BC  = _s("bc",  alignment=1, fontName="Helvetica-Bold")
_BL  = _s("bl",  alignment=0, fontName="Helvetica-Bold")
_TI  = _s("ti",  alignment=1, fontName="Helvetica-Bold", fontSize=8, leading=9)
_GR  = _s("gr",  alignment=1, fontName="Helvetica-Bold", fontSize=10, leading=11)
_VP  = _s("vp",  alignment=0, fontName="Helvetica-Bold", fontSize=9, leading=10)
_VPR = _s("vpr", alignment=2, fontName="Helvetica-Bold", fontSize=9, leading=10)

# ── helpers ───────────────────────────────────────────────────────────────────
def _fmt_cnpj(cnpj):
    d = "".join(c for c in (cnpj or "") if c.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return cnpj

def _fmt_cpf_cnpj(doc):
    d = "".join(c for c in (doc or "") if c.isdigit())
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return _fmt_cnpj(d)
    return doc

def _fmt_chave(chave):
    d = "".join(c for c in (chave or "") if c.isdigit())
    return " ".join(d[i:i+4] for i in range(0, len(d), 4))

def _br(v):
    try:
        return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)

def _fmt_qtd(qtd):
    if qtd == int(qtd):
        return f"{int(qtd)},00"
    s = f"{qtd:.3f}".rstrip("0")
    if len(s.split(".")[1]) < 2:
        s += "0"
    return s.replace(".", ",")

def _fmt_data(dt):
    if dt is None:
        return ""
    try:
        if hasattr(dt, "strftime"):
            return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        pass
    return str(dt)

def _hr():
    return HRFlowable(width="100%", thickness=0.5, color=colors.black,
                      dash=(4, 3), spaceAfter=1, spaceBefore=1)

def _sp(h=1):
    return Spacer(1, h * MM)

def _p(texto, estilo=None):
    return Paragraph(str(texto or ""), estilo or _L)

def _qr(url, size_mm=32):
    qr = qrcode.QRCode(version=None,
                       error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    s = size_mm * MM
    return Image(buf, width=s, height=s)

def _tabela_2col(rows, w_label=None):
    wl = w_label or _IW * 0.65
    wr = _IW - wl
    tbl = Table(rows, colWidths=[wl, wr], hAlign="CENTER")
    tbl.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 7),
        ("LEADING",       (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 1),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("ALIGN",         (1, 0), (1, -1), "RIGHT"),
    ]))
    return tbl

_TPAG = {
    "01": "Dinheiro", "02": "Cheque", "03": "Cartão de Crédito",
    "04": "Cartão de Débito", "05": "Crédito Loja", "10": "Vale Alimentação",
    "11": "Vale Refeição", "12": "Vale Presente", "13": "Vale Combustível",
    "15": "Boleto Bancário", "17": "PIX", "90": "Sem Pagamento", "99": "Outros",
}

def _pag_nome(codigo):
    return _TPAG.get(str(codigo).zfill(2), f"Forma {codigo}")

# ── extração do XML ───────────────────────────────────────────────────────────
def _parse_xml(xml_str):
    """Extrai itens e pagamentos do XML autorizado da NFC-e."""
    if not xml_str:
        return [], []
    try:
        root = etree.fromstring(xml_str.encode() if isinstance(xml_str, str) else xml_str)
    except Exception:
        return [], []

    itens = []
    for det in root.findall(".//nfe:det", _NS):
        prod = det.find("nfe:prod", _NS)
        if prod is None:
            continue
        itens.append({
            "codigo":     prod.findtext("nfe:cProd", "", _NS),
            "nome":       prod.findtext("nfe:xProd", "", _NS),
            "qtde":       float(prod.findtext("nfe:qCom", "0", _NS) or 0),
            "unidade":    prod.findtext("nfe:uCom", "UN", _NS),
            "preco_unit": float(prod.findtext("nfe:vUnCom", "0", _NS) or 0),
            "preco_total":float(prod.findtext("nfe:vProd", "0", _NS) or 0),
        })

    pagamentos = []
    for det_pag in root.findall(".//nfe:detPag", _NS):
        pagamentos.append({
            "forma": det_pag.findtext("nfe:tPag", "01", _NS),
            "valor": float(det_pag.findtext("nfe:vPag", "0", _NS) or 0),
        })

    return itens, pagamentos

# ── montagem do conteúdo ─────────────────────────────────────────────────────
def _build_story(nota_fiscal):
    story = []
    empresa = nota_fiscal.empresa
    itens, pagamentos = _parse_xml(nota_fiscal.xml_assinado)

    # — cabeçalho —
    story.append(_p(empresa.nome_fantasia or empresa.nome, _GR))
    end = ", ".join(filter(None, [
        empresa.logradouro, empresa.numero,
        empresa.bairro, empresa.cidade, empresa.uf,
    ]))
    if end.strip():
        story.append(_p(end, _C))
    story.append(_p(f"CNPJ: {_fmt_cnpj(empresa.cnpj)}  IE: {empresa.inscricao_estadual or ''}", _C))
    story.append(_hr())

    # — título —
    story.append(_p("DANFE NFC-e Documento Auxiliar da", _TI))
    story.append(_p("Nota Fiscal de Consumidor Eletrônica", _TI))
    story.append(_hr())

    # — tabela de itens —
    _nb = " "
    header = [
        _p("CÓD",           _BC),
        _p("DESCRIÇÃO",     _BL),
        _p("QTDE",          _BC),
        _p("UN",            _BC),
        _p(f"VL{_nb}UNIT",  _BC),
        _p(f"VL{_nb}TOTAL", _BC),
    ]
    _estilo_itens = [
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 6),
        ("LEADING",       (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 1),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 1),
        ("RIGHTPADDING",  (5, 0), ( 5, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("ALIGN",         (0, 0), ( 0, -1), "CENTER"),
        ("ALIGN",         (1, 0), ( 1, -1), "LEFT"),
        ("ALIGN",         (2, 0), ( 2, -1), "RIGHT"),
        ("ALIGN",         (3, 0), ( 3, -1), "CENTER"),
        ("ALIGN",         (4, 0), (-1, -1), "RIGHT"),
    ]

    tbl_header = Table([header], colWidths=_COL_ITENS, hAlign="CENTER")
    tbl_header.setStyle(TableStyle(_estilo_itens + [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.append(tbl_header)

    valor_subtotal = 0.0
    data_rows = []
    for item in itens:
        valor_subtotal += item["preco_total"]
        data_rows.append([
            _p(item["codigo"],              _C),
            _p(item["nome"],                _L),
            _p(_fmt_qtd(item["qtde"]),      _R),
            _p(item["unidade"],             _C),
            _p(_br(item["preco_unit"]),     _R),
            _p(_br(item["preco_total"]),    _R),
        ])

    if data_rows:
        tbl_data = Table(data_rows, colWidths=_COL_ITENS, hAlign="CENTER")
        tbl_data.setStyle(TableStyle(_estilo_itens))
        story.append(tbl_data)
    story.append(_hr())

    # — totais —
    valor_nf = float(nota_fiscal.valor_total)
    desconto = round(valor_subtotal - valor_nf, 2)
    tot_rows = [
        [_p("Qtd. Total de Itens", _BL), _p(str(len(itens)), _R)],
        [_p("Valor Total R$"),            _p(_br(valor_subtotal), _R)],
    ]
    if desconto > 0.005:
        tot_rows.append([_p("Desconto R$"), _p(f"-{_br(desconto)}", _R)])
    tot_rows.append([_p("Valor a Pagar R$", _VP), _p(_br(valor_nf), _VPR)])
    story.append(_tabela_2col(tot_rows))
    story.append(_hr())

    # — pagamentos —
    if not pagamentos:
        pagamentos = [{"forma": nota_fiscal.forma_pagamento, "valor": valor_nf}]
    soma_pag = sum(p["valor"] for p in pagamentos)
    pag_rows = [[_p("FORMA PAGAMENTO", _BL), _p("VALOR PAGO R$", _s("bpr", alignment=2, fontName="Helvetica-Bold"))]]
    for pag in pagamentos:
        pag_rows.append([_p(_pag_nome(pag["forma"])), _p(_br(pag["valor"]), _R)])
    troco = round(max(0.0, soma_pag - valor_nf), 2)
    if troco > 0:
        pag_rows.append([_p("Troco R$"), _p(_br(troco), _R)])
    story.append(_tabela_2col(pag_rows))
    story.append(_hr())

    # — chave de acesso —
    story.append(_p("Consulte pela Chave de Acesso em", _BC))
    story.append(_p("www.sefaz.ma.gov.br/nfce/consulta", _C))
    story.append(_sp(1))
    story.append(_p(_fmt_chave(nota_fiscal.chave), _C))

    # — consumidor —
    if nota_fiscal.cliente and getattr(nota_fiscal.cliente, "cpf_cnpj", None):
        story.append(_hr())
        story.append(_p(f"CONSUMIDOR - CPF: {_fmt_cpf_cnpj(nota_fiscal.cliente.cpf_cnpj)}", _C))
        story.append(_p(nota_fiscal.cliente.nome or "", _C))

    story.append(_hr())

    # — dados da NFC-e —
    if (nota_fiscal.ambiente or "homologacao") == "homologacao":
        story.append(_p("*** AMBIENTE DE HOMOLOGAÇÃO — SEM VALOR FISCAL ***", _BC))
    story.append(_p(
        f"NFCe n. {nota_fiscal.numero:09d}  Série {nota_fiscal.serie}  "
        f"{_fmt_data(nota_fiscal.data_emissao)}",
        _BC,
    ))
    story.append(_p("Via Consumidor", _BC))

    if nota_fiscal.protocolo_autorizacao:
        story.append(_p(f"Protocolo de Autorização: {nota_fiscal.protocolo_autorizacao}", _C))
        story.append(_p(f"Data de Autorização: {_fmt_data(nota_fiscal.data_emissao)}", _C))

    # — QR-Code —
    if nota_fiscal.qrcode_url:
        story.append(_sp())
        try:
            qi = _qr(nota_fiscal.qrcode_url, size_mm=32)
            qi.hAlign = "CENTER"
            story.append(qi)
        except Exception:
            story.append(_p(nota_fiscal.qrcode_url, _C))

    story.append(_hr())
    story.append(_p("Tributos Totais Incidentes (Lei Federal 12.741/2012): R$ -----", _C))

    return story


# ── geração do PDF com altura dinâmica ───────────────────────────────────────
class _MeasureDoc(SimpleDocTemplate):
    min_frame_y: float = 9999 * MM

    def afterFlowable(self, _):
        if self.frame and hasattr(self.frame, "_y"):
            self.min_frame_y = min(self.min_frame_y, self.frame._y)


def gerar_danfe_nfce(nota_fiscal) -> bytes:
    """Gera o DANFE NFC-e em formato PDF (80 mm) e devolve os bytes."""
    buf1 = BytesIO()
    doc1 = _MeasureDoc(
        buf1, pagesize=(_LARGURA, 9999 * MM),
        leftMargin=_MARGEM_H, rightMargin=_MARGEM_H,
        topMargin=_MARGEM_V, bottomMargin=_MARGEM_V,
    )
    doc1.build(_build_story(nota_fiscal))
    altura = (9999 * MM - doc1.min_frame_y) + _MARGEM_V + 3 * MM

    buf2 = BytesIO()
    doc2 = SimpleDocTemplate(
        buf2, pagesize=(_LARGURA, max(altura, 60 * MM)),
        leftMargin=_MARGEM_H, rightMargin=_MARGEM_H,
        topMargin=_MARGEM_V, bottomMargin=_MARGEM_V,
    )
    doc2.build(_build_story(nota_fiscal))
    buf2.seek(0)
    return buf2.read()
