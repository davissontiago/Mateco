from django.db import models

class NotaFiscal(models.Model):
    # ID interno da Nuvem Fiscal (opcional, pode ser útil)
    id_nota = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID Nuvem Fiscal")
    
    # Dados da Nota
    numero = models.IntegerField(default=0, verbose_name="Número")
    serie = models.IntegerField(default=0, verbose_name="Série")
    chave = models.CharField(max_length=50, blank=True, null=True, verbose_name="Chave de Acesso")
    
    # Valores e Status
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Total (R$)")
    status = models.CharField(max_length=50, default='PENDENTE')
    
    # Arquivos (PDF e XML)
    url_pdf = models.URLField(max_length=500, blank=True, null=True, verbose_name="Link do PDF")
    url_xml = models.URLField(max_length=500, blank=True, null=True, verbose_name="Link do XML")
    
    data_emissao = models.DateTimeField(auto_now_add=True, verbose_name="Data Emissão")

    def __str__(self):
        return f"Nota {self.numero} - R$ {self.valor_total}"

    class Meta:
        ordering = ['-data_emissao']