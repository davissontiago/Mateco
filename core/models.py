from django.db import models

class NotaFiscal(models.Model):
    id_nota = models.CharField(max_length=100, unique=True, verbose_name="ID Nuvem Fiscal")
    numero = models.IntegerField(verbose_name="Número")
    serie = models.IntegerField(verbose_name="Série")
    data_emissao = models.DateTimeField(auto_now_add=True, verbose_name="Data Emissão")
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor (R$)")
    status = models.CharField(max_length=50)

    def __str__(self):
        return f"Nota {self.numero} - R$ {self.valor}"

    class Meta:
        ordering = ['-data_emissao'] # Garante que a mais recente apareça primeiro