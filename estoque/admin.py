from django.contrib import admin
from .models import Produto

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'preco', 'estoque_atual', 'ncm')
    search_fields = ('nome', 'codigo')