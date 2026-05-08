"""
Comunicação direta com a SEFAZ via erpbrasil.edoc + nfelib + signxml.

Emissão e cancelamento de NFC-e para MA (SVRS).
Adaptado de matech-backend/fiscal/sefaz_service.py para o modelo Empresa do NotasAuto.

CONTRATO DE INTERFACE (compatível com NuvemFiscalService)
=========================================================================

`emitir_nfce(empresa, itens_carrinho, pagamentos, troco=0.0, cliente=None)`
    Retorna tupla `(sucesso: bool, resposta, valor_total: float)`.

    Se sucesso=True, `resposta` é um dict contendo:
        - "id"                    (str) — chave de 44 dígitos
        - "ambiente"              (str) — "producao" ou "homologacao"
        - "numero"                (int)
        - "serie"                 (int)
        - "chave"                 (str) — 44 dígitos
        - "status"                (str) — "autorizado"
        - "data_emissao"          (str ISO-8601)
        - "qrcode_url"            (str)
        - "xml_protocolo"         (str)
        - "protocolo_autorizacao" (str)

    Se sucesso=False, `resposta` é uma string com o motivo do erro.

`cancelar_nfce(empresa, nota_fiscal, justificativa)`
    Retorna tupla `(sucesso: bool, mensagem: str)`.

`consultar_nfce_por_chave(empresa, chave)`
    Retorna dict compatível com `resposta` de `emitir_nfce` ou None.
"""

import base64
import hashlib
import logging
import re
from datetime import datetime
from types import SimpleNamespace

logger = logging.getLogger(__name__)

from django.utils import timezone

from erpbrasil.assinatura.certificado import Certificado
from erpbrasil.edoc.nfce import NFCe
from erpbrasil.edoc.nfe import WS_NFE_AUTORIZACAO, localizar_url
from erpbrasil.transmissao import TransmissaoSOAP
from lxml import etree
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from core.crypto import decrypt_bytes, decrypt_str
from core.sefaz_payload import montar_nfce

# --- Monkey-patch: erpbrasil.edoc ESTADO_WS para MA ---
# Bug upstream: MA não tem entradas mod-specific ("55"/"65") no mapeamento de
# webservices. Sem o patch, NFC-e (mod=65) cai no endpoint de NF-e, causando
# rejeição 450.
from erpbrasil.edoc.nfe import ESTADO_WS as _ESTADO_WS

_SVRS_PATHS = {
    "NfeInutilizacao": "ws/nfeinutilizacao/nfeinutilizacao4.asmx?wsdl",
    "NfeConsultaProtocolo": "ws/NfeConsulta/NfeConsulta4.asmx?wsdl",
    "NfeStatusServico": "ws/NfeStatusServico/NfeStatusServico4.asmx?wsdl",
    "RecepcaoEvento": "ws/recepcaoevento/recepcaoevento4.asmx?wsdl",
    "NfeAutorizacao": "ws/NfeAutorizacao/NFeAutorizacao4.asmx?wsdl",
    "NfeRetAutorizacao": "ws/NfeRetAutorizacao/NFeRetAutorizacao4.asmx?wsdl",
}

_ESTADO_WS["MA"] = (
    {
        "55": {
            1: {"servidor": "nfe.svrs.rs.gov.br", **_SVRS_PATHS},
            2: {"servidor": "nfe-homologacao.svrs.rs.gov.br", **_SVRS_PATHS},
        },
        "65": {
            1: {"servidor": "nfce.svrs.rs.gov.br", **_SVRS_PATHS},
            2: {"servidor": "nfce-homologacao.svrs.rs.gov.br", **_SVRS_PATHS},
        },
    },
    _ESTADO_WS["MA"][1],
)

# URLs do portal NFC-e da SEFAZ MA (tabUfUrl.xml)
_QRCODE_BASE_MA = {
    "1": "http://www.nfce.sefaz.ma.gov.br/portal/consultarNFCe.jsp",
    "2": "http://www.hom.nfce.sefaz.ma.gov.br/portal/consultarNFCe.jsp",
}
_URL_CHAVE_MA = "www.sefaz.ma.gov.br/nfce/consulta"


def _gerar_qrcode_url(nfce, empresa) -> tuple[str, str]:
    """
    Gera (qrcode_url, url_chave) para infNFeSupl.
    Cálculo NT 2015.003 v2: SHA1(chave44|2|tpAmb|csc_id + csc_code).upper()
    """
    is_producao = empresa.ambiente == "producao"
    tp_amb = "1" if is_producao else "2"
    url_base = _QRCODE_BASE_MA[tp_amb]

    chave44 = nfce.infNFe.Id.replace("NFe", "")

    csc_id_raw = empresa.csc_id_producao if is_producao else empresa.csc_id_homologacao
    csc_token_ciphered = empresa.csc_token_producao if is_producao else empresa.csc_token_homologacao
    csc_id = str(int(csc_id_raw or 0))
    csc_code = decrypt_str(bytes(csc_token_ciphered)) if csc_token_ciphered else ""

    pre_qrcode = f"{chave44}|2|{tp_amb}|{csc_id}"
    c_hash = hashlib.sha1((pre_qrcode + csc_code).encode("utf-8")).hexdigest().upper()

    return f"{url_base}?p={pre_qrcode}|{c_hash}", _URL_CHAVE_MA


_NFE_NS = "http://www.portalfiscal.inf.br/nfe"
_xsdata_serializer = XmlSerializer(config=SerializerConfig(xml_declaration=False))
_SOAP_BODY_RE = re.compile(
    r"<soap:Body>(.*?)</soap:Body>|<[a-zA-Z0-9:]*Body[^>]*>(.*?)</[a-zA-Z0-9:]*Body>",
    re.DOTALL,
)


def _patch_export(nfe_obj):
    """Adiciona export() (interface generateDS) ao dataclass xsdata para compatibilidade com erpbrasil.edoc."""
    def export(outfile, level=0, pretty_print=False, namespacedef_='', **kw):
        xml_str = _xsdata_serializer.render(nfe_obj, ns_map={None: _NFE_NS})
        outfile.write(xml_str)
    nfe_obj.export = export


def _xml_to_obj(element):
    """Converte lxml Element em SimpleNamespace com acesso por atributo."""
    obj = SimpleNamespace()
    for attr_name, attr_val in element.attrib.items():
        setattr(obj, attr_name, attr_val)
    children_by_tag = {}
    for child in element:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        children_by_tag.setdefault(tag, []).append(child)
    for tag, children in children_by_tag.items():
        if len(children) == 1:
            child = children[0]
            val = _xml_to_obj(child) if len(child) > 0 else child.text
            setattr(obj, tag, val)
        else:
            setattr(obj, tag, [
                _xml_to_obj(c) if len(c) > 0 else c.text for c in children
            ])
    return obj


def _enviar_nfce(edoc, nfce):
    """Envia NFC-e via lxml puro, sem dependência de erpbrasil.nfelib_legacy (generateDS)."""
    _patch_export(nfce)
    xml_assinado = edoc.assina_raiz(nfce, nfce.infNFe.Id)

    envi = etree.Element("enviNFe", nsmap={None: _NFE_NS}, versao=edoc.versao)
    etree.SubElement(envi, "idLote").text = datetime.now().strftime("%Y%m%d%H%M%S")
    etree.SubElement(envi, "indSinc").text = "1" if edoc.envio_sincrono else "0"
    envi.append(etree.fromstring(xml_assinado))

    url = localizar_url(WS_NFE_AUTORIZACAO, str(edoc.uf), edoc.mod, int(edoc.ambiente))
    with edoc._transmissao.cliente(url):
        retorno = edoc._transmissao.enviar("nfeAutorizacaoLote", envi)

    retorno.raise_for_status()

    body_match = _SOAP_BODY_RE.search(retorno.text.replace("\n", ""))
    if not body_match:
        return SimpleNamespace(resposta=None, envio_raiz=envi)

    xml_body = body_match.group(1) or body_match.group(2)
    resp_tree = etree.fromstring(xml_body.encode("utf-8"))

    ret_el = resp_tree
    for el in resp_tree.iter():
        if "retEnviNFe" in el.tag:
            ret_el = el
            break

    resposta = _xml_to_obj(ret_el)

    resultado = SimpleNamespace(
        envio_raiz=envi,
        envio_xml=etree.tostring(envi, encoding="unicode"),
        retorno=retorno,
        resposta=resposta,
        protocolo=None,
        processo=None,
        processo_xml=None,
    )

    prot = getattr(resposta, "protNFe", None)
    if prot is not None:
        if isinstance(prot, list):
            prot = prot[0]
        resultado.protocolo = prot

        nfe_el = envi.find(f"{{{_NFE_NS}}}NFe")
        prot_el = ret_el.find(f".//{{{_NFE_NS}}}protNFe")
        if nfe_el is not None:
            nfe_proc = etree.Element(
                f"{{{_NFE_NS}}}nfeProc", versao=edoc.versao, nsmap={None: _NFE_NS},
            )
            nfe_proc.append(nfe_el)
            if prot_el is not None:
                nfe_proc.append(prot_el)
            resultado.processo = nfe_proc
            resultado.processo_xml = etree.tostring(nfe_proc, encoding="unicode")

    return resultado


UF_CODIGO_IBGE = {
    "AC": 12, "AL": 27, "AM": 13, "AP": 16, "BA": 29, "CE": 23,
    "DF": 53, "ES": 32, "GO": 52, "MA": 21, "MG": 31, "MS": 50,
    "MT": 51, "PA": 15, "PB": 25, "PE": 26, "PI": 22, "PR": 41,
    "RJ": 33, "RN": 24, "RO": 11, "RR": 14, "RS": 43, "SC": 42,
    "SE": 28, "SP": 35, "TO": 17,
}


class SefazService:
    """Comunicação direta com a SEFAZ para emissão e cancelamento de NFC-e."""

    @classmethod
    def _carregar_certificado(cls, empresa):
        is_producao = empresa.ambiente == "producao"
        pfx_ciphered = empresa.certificado_a1_pfx_producao if is_producao else empresa.certificado_a1_pfx_homologacao
        senha_ciphered = empresa.certificado_a1_senha_producao if is_producao else empresa.certificado_a1_senha_homologacao
        if not pfx_ciphered or not senha_ciphered:
            return None

        pfx_bytes = decrypt_bytes(bytes(pfx_ciphered))
        senha = decrypt_str(bytes(senha_ciphered))
        pfx_b64 = base64.b64encode(pfx_bytes)

        return Certificado(arquivo=pfx_b64, senha=senha, raise_expirado=True)

    @classmethod
    def _get_transmissao(cls, empresa):
        certificado = cls._carregar_certificado(empresa)
        if certificado is None:
            return None
        return TransmissaoSOAP(certificado=certificado, cache=True)

    @classmethod
    def _get_edoc(cls, empresa):
        transmissao = cls._get_transmissao(empresa)
        if transmissao is None:
            return None

        is_producao = empresa.ambiente == "producao"
        ambiente_str = "1" if is_producao else "2"

        csc_id = empresa.csc_id_producao if is_producao else empresa.csc_id_homologacao
        csc_token_ciphered = empresa.csc_token_producao if is_producao else empresa.csc_token_homologacao
        csc_code_plain = decrypt_str(bytes(csc_token_ciphered)) if csc_token_ciphered else None

        uf_sigla = (empresa.uf or "").upper()
        uf_codigo = UF_CODIGO_IBGE.get(uf_sigla)
        if uf_codigo is None:
            raise ValueError(f"UF '{uf_sigla}' não mapeada para código IBGE em SefazService.")

        return NFCe(
            transmissao=transmissao,
            uf=uf_codigo,
            versao="4.00",
            ambiente=ambiente_str,
            mod="65",
            qrcode_versao="2",
            csc_token=csc_id,
            csc_code=csc_code_plain,
            envio_sincrono=True,
        )

    @classmethod
    def _proximo_numero(cls, empresa):
        from core.models import NotaFiscal

        is_producao = empresa.ambiente == "producao"
        serie = empresa.serie_nfce_producao if is_producao else empresa.serie_nfce_homologacao
        ultima = (
            NotaFiscal.objects
            .filter(empresa=empresa, serie=serie, ambiente=empresa.ambiente)
            .order_by("-numero")
            .first()
        )
        ultimo_db = ultima.numero if ultima else 0
        ultimo_manual = empresa.numero_nfce_producao if is_producao else empresa.numero_nfce_homologacao
        numero = max(ultimo_db, ultimo_manual) + 1
        return serie, numero

    @classmethod
    def emitir_nfce(cls, empresa, itens_carrinho, pagamentos, troco=0.0, cliente=None, desconto_global=0.0):
        edoc = cls._get_edoc(empresa)
        if edoc is None:
            return False, "Certificado A1 não configurado para este ambiente.", 0.0

        serie, numero = cls._proximo_numero(empresa)

        try:
            nfce = montar_nfce(
                empresa=empresa,
                itens_carrinho=itens_carrinho,
                pagamentos=pagamentos,
                cliente=cliente,
                numero=numero,
                serie=serie,
                desconto_global=desconto_global,
            )
        except Exception as exc:
            return False, f"Erro ao montar NFC-e: {exc}", 0.0

        valor_total = float(nfce.infNFe.total.ICMSTot.vNF)

        try:
            qrcode_url, url_chave = _gerar_qrcode_url(nfce, empresa)
            from nfelib.nfe.bindings.v4_0.nfe_v4_00 import Nfe as _NfeBinding
            nfce.infNFeSupl = _NfeBinding.InfNfeSupl(
                qrCode=qrcode_url,
                urlChave=url_chave,
            )
        except Exception as exc:
            logger.error("Erro ao montar infNFeSupl: %s", exc)

        try:
            proc_envio = _enviar_nfce(edoc, nfce)
        except Exception as exc:
            return False, f"Falha de comunicação com SEFAZ: {exc}", 0.0

        resposta = getattr(proc_envio, "resposta", None)
        if resposta is None:
            return False, "Resposta vazia da SEFAZ.", 0.0

        cstat_lote = str(getattr(resposta, "cStat", "") or "")
        if cstat_lote not in ("103", "104"):
            motivo = getattr(resposta, "xMotivo", "") or ""
            return False, f"Rejeição do lote [{cstat_lote}]: {motivo}".strip(), 0.0

        protocolo = getattr(proc_envio, "protocolo", None)
        if protocolo is None or getattr(protocolo, "infProt", None) is None:
            return False, "Protocolo de autorização ausente na resposta.", 0.0

        inf_prot = protocolo.infProt
        cstat_prot = str(getattr(inf_prot, "cStat", "") or "")
        xmotivo = getattr(inf_prot, "xMotivo", "") or ""

        if cstat_prot != "100":
            if cstat_prot == "539":
                chave_gerada = nfce.infNFe.Id.replace("NFe", "")
                recuperada = cls.consultar_nfce_por_chave(empresa, chave_gerada)
                if recuperada is not None:
                    recuperada["numero"] = numero
                    recuperada["serie"] = serie
                    return True, recuperada, valor_total
            return False, f"Rejeição SEFAZ [{cstat_prot}]: {xmotivo}", 0.0

        chave = getattr(inf_prot, "chNFe", "") or nfce.infNFe.Id.replace("NFe", "")
        n_prot = getattr(inf_prot, "nProt", "") or ""
        dh_recbto = getattr(inf_prot, "dhRecbto", None) or datetime.now().astimezone().isoformat()

        try:
            qrcode_url = edoc.monta_qrcode(chave)
        except Exception:
            qrcode_url = ""

        xml_assinado = getattr(proc_envio, "processo_xml", None)
        if xml_assinado is None and hasattr(proc_envio, "processo"):
            try:
                xml_assinado = etree.tostring(proc_envio.processo, encoding="unicode")
            except Exception:
                xml_assinado = ""

        return True, {
            "id": chave,
            "ambiente": empresa.ambiente,
            "numero": numero,
            "serie": serie,
            "chave": chave,
            "status": "autorizado",
            "data_emissao": dh_recbto,
            "qrcode_url": qrcode_url,
            "xml_protocolo": xml_assinado or "",
            "protocolo_autorizacao": n_prot,
        }, valor_total

    @classmethod
    def cancelar_nfce(cls, empresa, nota_fiscal, justificativa):
        just = (justificativa or "").strip()
        if len(just) < 15:
            return False, "Justificativa deve ter ao menos 15 caracteres."

        chave = getattr(nota_fiscal, "chave", None)
        protocolo = getattr(nota_fiscal, "protocolo_autorizacao", None)
        if not chave or not protocolo:
            return False, "Nota sem chave ou protocolo de autorização."

        edoc = cls._get_edoc(empresa)
        if edoc is None:
            return False, "Certificado A1 não configurado para este ambiente."

        try:
            raiz = edoc.cancela_documento(
                chave=chave,
                protocolo_autorizacao=protocolo,
                justificativa=just,
            )
            proc = edoc.enviar_lote_evento([raiz])
        except Exception as exc:
            return False, f"Falha de comunicação com SEFAZ: {exc}"

        resposta = getattr(proc, "resposta", None)
        if resposta is None:
            return False, "Resposta vazia da SEFAZ."

        cstat_lote = str(getattr(resposta, "cStat", "") or "")
        if cstat_lote != "128":
            motivo = getattr(resposta, "xMotivo", "") or ""
            return False, f"Rejeição do lote de evento [{cstat_lote}]: {motivo}".strip()

        ret_evento_list = getattr(resposta, "retEvento", None)
        if not ret_evento_list:
            return False, "Resposta do evento de cancelamento ausente."
        ret_evento = ret_evento_list[0] if isinstance(ret_evento_list, list) else ret_evento_list
        inf_evento = getattr(ret_evento, "infEvento", None)
        if inf_evento is None:
            return False, "infEvento ausente na resposta de cancelamento."

        cstat_ev = str(getattr(inf_evento, "cStat", "") or "")
        xmotivo = getattr(inf_evento, "xMotivo", "") or ""
        if cstat_ev not in ("135", "136", "155"):
            return False, f"Rejeição cancelamento [{cstat_ev}]: {xmotivo}"

        n_prot_canc = getattr(inf_evento, "nProt", "") or ""
        xml_canc = getattr(proc, "processo_xml", None)
        if xml_canc is None:
            try:
                xml_canc = etree.tostring(proc.envio_raiz, encoding="unicode")
            except Exception:
                xml_canc = ""

        nota_fiscal.status = "cancelado"
        nota_fiscal.xml_cancelamento = xml_canc or ""
        nota_fiscal.protocolo_cancelamento = n_prot_canc
        nota_fiscal.data_cancelamento = timezone.now()
        nota_fiscal.save()

        return True, f"Nota cancelada com sucesso. Protocolo: {n_prot_canc}"

    @classmethod
    def consultar_nfce_por_chave(cls, empresa, chave):
        edoc = cls._get_edoc(empresa)
        if edoc is None:
            return None

        try:
            proc = edoc.consulta_documento(chave)
        except Exception:
            return None

        resposta = getattr(proc, "resposta", None)
        if resposta is None:
            return None

        cstat = str(getattr(resposta, "cStat", "") or "")
        if cstat != "100":
            return None

        prot_nfe = getattr(resposta, "protNFe", None)
        if prot_nfe is None:
            return None
        inf_prot = getattr(prot_nfe, "infProt", None)
        if inf_prot is None:
            return None

        chave_ret = getattr(inf_prot, "chNFe", "") or chave
        n_prot = getattr(inf_prot, "nProt", "") or ""
        dh_recbto = getattr(inf_prot, "dhRecbto", None) or ""

        try:
            qrcode_url = edoc.monta_qrcode(chave_ret)
        except Exception:
            qrcode_url = ""

        return {
            "id": chave_ret,
            "ambiente": empresa.ambiente,
            "numero": None,
            "serie": None,
            "chave": chave_ret,
            "status": "autorizado",
            "data_emissao": dh_recbto,
            "qrcode_url": qrcode_url,
            "xml_protocolo": "",
            "protocolo_autorizacao": n_prot,
        }
