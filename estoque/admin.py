from django.contrib import admin
from .models import Produto

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    """
    Configuração do painel administrativo para o Catálogo de Produtos.
    
    Permite o gerenciamento de estoque, preços e informações fiscais (NCM)
    essenciais para a emissão de notas fiscais.
    """

    # ==================================================
    # 1. VISUALIZAÇÃO NA LISTA (COLUNAS)
    # ==================================================
    # Exibe as informações principais na tabela de listagem
    list_display = (
        'nome', 
        'codigo', 
        'preco', 
        'estoque_atual', 
        'ncm'
    )

    # ==================================================
    # 2. FERRAMENTAS DE BUSCA E FILTRO
    # ==================================================
    # Permite buscar produtos pelo nome ou código interno
    search_fields = ('nome', 'codigo')
    
    # Adiciona filtros laterais para facilitar a navegação por faixas de preço
    # ou produtos sem estoque (útil quando o inventário crescer)
    list_filter = ('preco',)

    # ==================================================
    # 3. CONFIGURAÇÕES DE INTERFACE
    # ==================================================
    # Ordenação padrão alfabética pelo nome
    ordering = ('nome',)
    
    # Paginação para manter a performance do painel
    list_per_page = 50
    
    # Permite editar o estoque diretamente na lista sem precisar abrir o produto
    list_editable = ('estoque_atual', 'preco')