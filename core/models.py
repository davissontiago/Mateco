from django.db import models

class NotaFiscal(models.Model):
    """
    Representa uma Nota Fiscal emitida ou pendente no sistema.
    
    Este modelo armazena os dados básicos da nota, os identificadores retornados
    pela API da Nuvem Fiscal e os links para os documentos gerados (PDF/XML).
    """

    # ==================================================
    # 1. IDENTIFICADORES E CHAVES
    # ==================================================
    id_nota = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="ID Nuvem Fiscal"
    )
    numero = models.IntegerField(default=0, verbose_name="Número")
    serie = models.IntegerField(default=0, verbose_name="Série")
    chave = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="Chave de Acesso"
    )

    # ==================================================
    # 2. VALORES E STATUS
    # ==================================================
    valor_total = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Valor Total (R$)"
    )
    status = models.CharField(
        max_length=50, 
        default='PENDENTE',
        verbose_name="Status"
    )

    # ==================================================
    # 3. DOCUMENTOS E DATAS
    # ==================================================
    url_pdf = models.URLField(
        max_length=500, 
        blank=True, 
        null=True, 
        verbose_name="Link do PDF"
    )
    url_xml = models.URLField(
        max_length=500, 
        blank=True, 
        null=True, 
        verbose_name="Link do XML"
    )
    data_emissao = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Data de Emissão"
    )

    # ==================================================
    # 4. MÉTODOS E CONFIGURAÇÕES
    # ==================================================
    def __str__(self):
        """Retorna uma representação legível do objeto no Admin."""
        return f"Nota {self.numero} - R$ {self.valor_total}"

    class Meta:
        """Configurações adicionais do modelo."""
        ordering = ['-data_emissao']
        verbose_name = "Nota Fiscal"
        verbose_name_plural = "Notas Fiscais"