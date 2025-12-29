from django.contrib import admin
from .models import NotaFiscal

@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display = ('numero', 'serie', 'data_emissao', 'valor_total', 'status', 'id_nota')
    
    search_fields = ('numero', 'chave', 'id_nota')
    
    list_filter = ('status', 'data_emissao')
    
    ordering = ('-data_emissao',)