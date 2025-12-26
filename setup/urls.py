from django.contrib import admin
from django.urls import path
from core.views import home, emitir, emitir_nfce_view, baixar_pdf_view, listar_notas # <--- Adicione listar_notas aqui

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('emitir/', emitir, name='emitir'),
    
    # NOVA ROTA:
    path('historico/', listar_notas, name='listar_notas'),

    path('emitir-nota/', emitir_nfce_view, name='emitir_nota'),
    path('imprimir-nota/<str:id_nota>/', baixar_pdf_view, name='imprimir_nota'),
]