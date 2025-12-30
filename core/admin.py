from django.contrib import admin
from .models import NotaFiscal

@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    """
    Configuração do painel administrativo para Notas Fiscais.
    
    Permite visualizar o histórico de notas, filtrar por status/data
    e buscar por números identificadores.
    """

    # ==================================================
    # 1. VISUALIZAÇÃO NA LISTA (COLUNAS)
    # ==================================================
    # Define quais colunas aparecem na tabela principal
    list_display = (
        'numero',
        'serie',
        'data_emissao',
        'valor_total',
        'status',
        'id_nota',
    )

    # ==================================================
    # 2. FERRAMENTAS DE BUSCA E FILTRO
    # ==================================================
    # Campos onde a barra de pesquisa vai procurar
    search_fields = ('numero', 'chave', 'id_nota')
    
    # Filtros laterais (Sidebars)
    list_filter = ('status', 'data_emissao')

    # ==================================================
    # 3. COMPORTAMENTO E ORDENAÇÃO
    # ==================================================
    # Ordenação padrão (do mais recente para o mais antigo)
    ordering = ('-data_emissao',)
    
    # Limita quantos itens aparecem por página (evita travar se tiver mil notas)
    list_per_page = 25