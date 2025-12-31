from django.db import models
from core.models import Empresa

class Produto(models.Model):
    """
    Representa um item do inventário no sistema Mateco.
    
    Este modelo armazena informações comerciais e fiscais necessárias 
    tanto para o controle de estoque quanto para a emissão de NFC-e.
    """

    # Campo Novo: Vincula o produto a uma loja específica
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, verbose_name="Loja/Empresa")

    # ==================================================
    # 1. IDENTIFICAÇÃO DO PRODUTO
    # ==================================================
    nome = models.CharField(
        max_length=100, 
        verbose_name="Nome do Produto"
    )
    codigo = models.CharField(
        max_length=20, 
        verbose_name="Código (EAN/Ref)"
    )

    # ==================================================
    # 2. DADOS FINANCEIROS E FISCAIS
    # ==================================================
    preco = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Preço Unitário (R$)"
    )
    ncm = models.CharField(
        max_length=8, 
        verbose_name="NCM (Imposto)", 
        help_text="Código de 8 dígitos. Ex: 25232910 para Cimento"
    )

    # ==================================================
    # 3. CONTROLE DE INVENTÁRIO
    # ==================================================
    estoque_atual = models.IntegerField(
        default=0, 
        verbose_name="Qtd em Estoque"
    )

    # ==================================================
    # 4. MÉTODOS E CONFIGURAÇÕES
    # ==================================================
    def __str__(self):
        """Retorna a representação textual do produto para o sistema."""
        return f"{self.nome} (R$ {self.preco})"

    class Meta:
        """Configurações de exibição do modelo no banco e no Admin."""
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        unique_together = ('empresa', 'codigo')