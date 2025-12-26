from django.db import models

class Produto(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome do Produto")
    codigo = models.CharField(max_length=20, unique=True, verbose_name="Código (EAN/Ref)")
    preco = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço Unitário (R$)")
    ncm = models.CharField(max_length=8, verbose_name="NCM (Imposto)", help_text="Ex: 25232910 para Cimento")
    estoque_atual = models.IntegerField(default=0, verbose_name="Qtd em Estoque")

    def __str__(self):
        return f"{self.nome} (R$ {self.preco})"

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"