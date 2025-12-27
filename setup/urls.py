from django.contrib import admin
from django.urls import path
# Importe a nova view buscar_produtos
from core.views import home, emitir, emitir_nfce_view, baixar_pdf_view, listar_notas, buscar_produtos

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('emitir/', emitir, name='emitir'),
    path('historico/', listar_notas, name='listar_notas'),

    # --- NOVA ROTA DE PESQUISA ---
    path('api/produtos/', buscar_produtos, name='buscar_produtos'),

    path('emitir-nota/', emitir_nfce_view, name='emitir_nota'),
    path('imprimir-nota/<str:id_nota>/', baixar_pdf_view, name='imprimir_nota'),
]