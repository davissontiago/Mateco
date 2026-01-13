from django.db import models
from django.contrib.auth.models import User


# ==================================================
# 1. CADASTRO DE EMPRESAS (MULTI-TENANT)
# ==================================================
from django.db import models

class Empresa(models.Model):
    """
    Representa uma Loja ou Filial no sistema.
    Armazena os dados fiscais e credenciais de API específicos de cada unidade.
    """

    # --- CONSTANTES DE ESCOLHA ---
    AMBIENTE_CHOICES = [
        ("homologacao", "Homologação (Testes)"),
        ("producao", "Produção (Valendo!)"),
    ]

    CRT_CHOICES = [
        ("1", "1 - Simples Nacional"),
        ("2", "2 - Simples Nacional (excesso de sublimite)"),
        ("3", "3 - Regime Normal (Lucro Presumido/Real)"),
    ]

    # --- DADOS GERAIS ---
    nome_fantasia = models.CharField(max_length=100, verbose_name="Nome Fantasia")
    nome = models.CharField(max_length=100, verbose_name="Razão Social")
    cnpj = models.CharField(max_length=14, unique=True, verbose_name="CNPJ (apenas números)")
    inscricao_estadual = models.CharField(max_length=20, blank=True, null=True, verbose_name="Inscrição Estadual")
    
    # --- CONFIGURAÇÃO VISUAL ---
    cor_primaria = models.CharField(
        max_length=10,
        default="#10295a",
        verbose_name="Cor Primária (Hex)",
        help_text="Ex: #10295a para azul escuro",
    )
    cor_secundaria = models.CharField(
        max_length=10,
        default="#dd5114",
        verbose_name="Cor Secundária (Hex)",
        help_text="Ex: #dd5114 para laranja",
    )

    # --- DADOS FISCAIS ---
    crt = models.CharField(
        max_length=1,
        choices=CRT_CHOICES,
        default="1",
        verbose_name="Regime Tributário (CRT)",
    )
    
    # Campo do Ambiente (Preenchido conforme solicitado)
    ambiente = models.CharField(
        max_length=20, 
        choices=AMBIENTE_CHOICES, 
        default='homologacao',
        verbose_name="Ambiente Nuvem Fiscal"
    )

    # --- ENDEREÇO ---
    cep = models.CharField(max_length=9, verbose_name="CEP")
    logradouro = models.CharField(max_length=100, verbose_name="Endereço")
    numero = models.CharField(max_length=10, verbose_name="Número")
    bairro = models.CharField(max_length=50, verbose_name="Bairro")
    cidade = models.CharField(max_length=50, verbose_name="Cidade")
    uf = models.CharField(max_length=2, verbose_name="UF")
    
    # Campo do Código do Município (Preenchido conforme solicitado)
    cod_municipio = models.CharField(
        max_length=7, 
        default="2112209", 
        verbose_name="Código IBGE do Município",
        help_text="Consulte em: https://www.ibge.gov.br/explica/codigos-dos-municipios.php"
    )

    # --- CREDENCIAIS DE API (HOMOLOGAÇÃO) ---
    nuvem_client_id_homologacao = models.CharField(
        max_length=255, 
        blank=True, null=True, 
        verbose_name="Client ID (Nuvem Fiscal) - Testes"
    )
    nuvem_client_secret_homologacao = models.CharField(
        max_length=255, 
        blank=True, null=True,
        verbose_name="Client Secret (Nuvem Fiscal) - Testes"
    )
    
    # --- CREDENCIAIS DE API (PRODUÇÃO) ---
    nuvem_client_id_producao = models.CharField(
        max_length=255, 
        blank=True, null=True,
        verbose_name="Client ID (Nuvem Fiscal) - Real"
    )
    nuvem_client_secret_producao = models.CharField(
        max_length=255, 
        blank=True, null=True,
        verbose_name="Client Secret (Nuvem Fiscal) - Real"
    )

    def __str__(self):
        return f"{self.nome} ({self.get_ambiente_display()})"

    class Meta:
        verbose_name = "Empresa / Loja"
        verbose_name_plural = "Empresas / Lojas"


class Cliente(models.Model):
    """
    Representa o consumidor final ou empresa cliente.
    Vinculado a uma Empresa (Loja) específica para manter o isolamento dos dados.
    """

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, verbose_name="Empresa/Loja"
    )

    nome = models.CharField(max_length=100, verbose_name="Nome Completo / Razão Social")
    cpf_cnpj = models.CharField(
        max_length=20, verbose_name="CPF ou CNPJ", help_text="Apenas números"
    )

    # Contato (Opcional)
    email = models.EmailField(blank=True, null=True, verbose_name="E-mail")
    telefone = models.CharField(
        max_length=20, blank=True, null=True, verbose_name="Telefone/WhatsApp"
    )

    # Endereço (Importante para NF-e Grande, Opcional para NFC-e)
    cep = models.CharField(max_length=9, blank=True, null=True, verbose_name="CEP")
    endereco = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Endereço"
    )
    numero = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="Número"
    )
    bairro = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Bairro" 
    )
    cidade = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Cidade"
    )
    uf = models.CharField(max_length=2, blank=True, null=True, verbose_name="UF")
    
    cod_municipio = models.CharField(
        max_length=7, 
        blank=True, 
        null=True, 
        verbose_name="Código IBGE",
        help_text="Código de 7 dígitos. Ex: 2112209 para Timon-MA"
    )

    def __str__(self):
        return f"{self.nome} ({self.cpf_cnpj})"

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        # Garante que não tenha CPF duplicado DENTRO DA MESMA EMPRESA
        unique_together = ("empresa", "cpf_cnpj")


class NotaFiscal(models.Model):
    """
    Representa uma Nota Fiscal emitida ou pendente no sistema.
    Este modelo armazena os dados básicos da nota, os identificadores retornados
    pela API da Nuvem Fiscal e os links para os documentos gerados (PDF/XML).
    """

    AMBIENTE_CHOICES = [
        ('homologacao', 'Homologação (Testes)'),
        ('producao', 'Produção (Real)'),
    ]
    
    PAGAMENTO_CHOICES = [
        ('01', 'Dinheiro'),
        ('03', 'Cartão de Crédito'),
        ('04', 'Cartão de Débito'),
        ('17', 'PIX'),
    ]
    
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, verbose_name="Empresa Emitente"
    )
    
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Cliente (Opcional)",
    )
    
    forma_pagamento = models.CharField(
        max_length=2, 
        choices=PAGAMENTO_CHOICES, 
        default='01',
        verbose_name="Forma de Pagamento"
    )

    # ==================================================
    # 1. IDENTIFICADORES E CHAVES
    # ==================================================
    ambiente = models.CharField(
        max_length=20, 
        choices=AMBIENTE_CHOICES, 
        default='homologacao',
        verbose_name="Ambiente"
    )
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
