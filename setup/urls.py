from django.contrib import admin
from django.urls import path, include
from estoque.views import ProdutoListView, buscar_produtos, criar_produto, editar_produto, deletar_produto
from core.views import (
    home, 
    emitir, 
    listar_notas, 
    buscar_produtos, 
    emitir_nota,   
    imprimir_nota,
    listar_clientes, 
    cadastrar_cliente,
    verificar_status_nota
)

"""
Configuração de URLs do Projeto Mateco.

O array 'urlpatterns' roteia as requisições para as views correspondentes.
Para mais informações, veja: https://docs.djangoproject.com/en/5.x/topics/http/urls/
"""

urlpatterns = [
    # ==================================================
    # 1. INTERFACE ADMINISTRATIVA E AUTENTICAÇÃO
    # ==================================================
    # Painel de controle padrão do Django
    path('admin/', admin.site.urls),
    
    # Sistema de autenticação (Login, Logout, Password Reset)
    # Procura templates em registration/ por padrão
    path('accounts/', include('django.contrib.auth.urls')), 
    
    # ==================================================
    # 2. PÁGINAS DO SISTEMA (VIEWS HTML)
    # ==================================================
    # Página inicial / Dashboard
    path('', home, name='home'),
    
    # Tela de emissão de notas (PDV)
    path('emitir/', emitir, name='emitir'),
    
    # Histórico e listagem de notas fiscais
    path('notas/', listar_notas, name='listar_notas'),
    
    # Estoque (Nova Rota)
    path('produtos/', ProdutoListView.as_view(), name='listar_produtos'),
    path('produto/novo/', criar_produto, name='criar_produto'),
    path('produto/editar/<int:id>/', editar_produto, name='editar_produto'),
    path('produto/deletar/<int:id>/', deletar_produto, name='deletar_produto'),

    # ==================================================
    # 3. ENDPOINTS DE API E PROCESSAMENTO
    # ==================================================
    # Busca de produtos e simulação de carrinho
    path('api/produtos/', buscar_produtos, name='buscar_produtos'),
    
    # Processamento de emissão de NFC-e na Nuvem Fiscal
    path('emitir-nota/', emitir_nota, name='emitir_nota'), 
    
    # Verifcar notas:
    path('verificar_nota/', verificar_status_nota, name='verificar_nota'),
    
    # Geração e download do PDF da nota fiscal
    path('imprimir-nota/<int:nota_id>/', imprimir_nota, name='imprimir_nota'),
    
    # Gestão de Clientes
    path('clientes/', listar_clientes, name='listar_clientes'),
    path('clientes/novo/', cadastrar_cliente, name='cadastrar_cliente'),
    path('clientes/editar/<int:cliente_id>/', cadastrar_cliente, name='editar_cliente'),
]