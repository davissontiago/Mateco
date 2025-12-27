from django.contrib import admin
from .models import NotaFiscal

@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    # Campos que aparecem na lista (colunas)
    list_display = ('numero', 'serie', 'data_emissao', 'valor_total', 'status', 'id_nota')
    
    # Campos que você pode pesquisar na barra de busca
    search_fields = ('numero', 'chave', 'id_nota')
    
    # Filtros laterais (por data ou status)
    list_filter = ('status', 'data_emissao')
    
    # Ordenação padrão (mais recentes primeiro)
    ordering = ('-data_emissao',)