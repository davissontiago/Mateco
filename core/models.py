from django.db import models
from django.contrib.auth.models import User


# ==================================================
# 1. CADASTRO DE EMPRESAS (MULTI-TENANT)
# ==================================================
class Empresa(models.Model):
    """
    Representa uma Loja ou Filial no sistema.
    Armazena os dados fiscais e credenciais de API específicos de cada unidade.
    """

    # Opções de Regime Tributário (Padrão Sefaz)
    CRT_CHOICES = [
        ("1", "1 - Simples Nacional"),
        ("2", "2 - Simples Nacional (excesso de sublimite)"),
        ("3", "3 - Regime Normal (Lucro Presumido/Real)"),
    ]

    # Identificação
    nome_fantasia = models.CharField(max_length=100, verbose_name="Nome Fantasia")
    nome = models.CharField(max_length=100, verbose_name="Razão Social")
    cnpj = models.CharField(
        max_length=14, unique=True, verbose_name="CNPJ (apenas números)"
    )
    inscricao_estadual = models.CharField(
        max_length=20, blank=True, null=True, verbose_name="Inscrição Estadual"
    )
    cor_primaria = models.CharField(
        max_length=10,
        default="#10295a",
        verbose_name="Cor Primaria (Hex)",
        help_text="Ex: #FF0000 para vermelho",
    )
    cor_secundaria = models.CharField(
        max_length=10,
        default="#10295a",
        verbose_name="Cor Secundaria (Hex)",
        help_text="Ex: #FF0000 para vermelho",
    )

    # Campo adicionado: Regime Tributário
    crt = models.CharField(
        max_length=1,
        choices=CRT_CHOICES,
        default="1",
        verbose_name="Regime Tributário (CRT)",
    )

    # Endereço (Obrigatório para emissão de Nota)
    cep = models.CharField(max_length=9, verbose_name="CEP")
    logradouro = models.CharField(max_length=100, verbose_name="Endereço")
    numero = models.CharField(max_length=10, verbose_name="Número")
    bairro = models.CharField(max_length=50, verbose_name="Bairro")
    cidade = models.CharField(max_length=50, verbose_name="Cidade")
    uf = models.CharField(max_length=2, verbose_name="UF")

    # Credenciais da API (Antes ficavam no .env, agora cada loja tem a sua)
    nuvem_client_id = models.CharField(
        max_length=255, verbose_name="Client ID (Nuvem Fiscal)"
    )
    nuvem_client_secret = models.CharField(
        max_length=255, verbose_name="Client Secret (Nuvem Fiscal)"
    )

    def __str__(self):
        return f"{self.nome} ({self.cnpj})"

    class Meta:
        verbose_name = "Empresa / Loja"
        verbose_name_plural = "Empresas / Lojas"


class NotaFiscal(models.Model):
    """
    Representa uma Nota Fiscal emitida ou pendente no sistema.

    Este modelo armazena os dados básicos da nota, os identificadores retornados
    pela API da Nuvem Fiscal e os links para os documentos gerados (PDF/XML).
    """

    # Campo Novo:
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, verbose_name="Empresa Emitente"
    )

    # ==================================================
    # 1. IDENTIFICADORES E CHAVES
    # ==================================================
    id_nota = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="ID Nuvem Fiscal"
    )
    numero = models.IntegerField(default=0, verbose_name="Número")
    serie = models.IntegerField(default=0, verbose_name="Série")
    chave = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Chave de Acesso"
    )

    # ==================================================
    # 2. VALORES E STATUS
    # ==================================================
    valor_total = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Valor Total (R$)"
    )
    status = models.CharField(max_length=50, default="PENDENTE", verbose_name="Status")

    # ==================================================
    # 3. DOCUMENTOS E DATAS
    # ==================================================
    url_pdf = models.URLField(
        max_length=500, blank=True, null=True, verbose_name="Link do PDF"
    )
    url_xml = models.URLField(
        max_length=500, blank=True, null=True, verbose_name="Link do XML"
    )
    data_emissao = models.DateTimeField(
        auto_now_add=True, verbose_name="Data de Emissão"
    )

    # ==================================================
    # 4. MÉTODOS E CONFIGURAÇÕES
    # ==================================================
    def __str__(self):
        """Retorna uma representação legível do objeto no Admin."""
        return f"Nota {self.numero} - R$ {self.valor_total}"

    class Meta:
        """Configurações adicionais do modelo."""

        ordering = ["-data_emissao"]
        verbose_name = "Nota Fiscal"
        verbose_name_plural = "Notas Fiscais"


# ==================================================
# 3. PERFIL DO USUÁRIO (VÍNCULO COM A EMPRESA)
# ==================================================
class PerfilUsuario(models.Model):
    """
    Estende o usuário padrão do Django para vinculá-lo a uma Empresa.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, verbose_name="Empresa/Loja"
    )

    def __str__(self):
        return f"{self.user.username} -> {self.empresa.nome}"
