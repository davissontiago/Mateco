from django.contrib import admin
from django.urls import path
from core.views import home, emitir, emitir_nfce_view, baixar_pdf_view # <--- Adicione baixar_pdf_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('emitir/', emitir, name='emitir'),
    path('emitir-nota/', emitir_nfce_view, name='emitir_nota'),
    
    # Nova rota que o botão vai chamar para ver o PDF
    path('imprimir-nota/<str:id_nota>/', baixar_pdf_view, name='imprimir_nota'),
]