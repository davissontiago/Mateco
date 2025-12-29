from django.contrib import admin
from django.urls import path
from core.views import (
    home, 
    emitir, 
    listar_notas, 
    buscar_produtos, 
    emitir_nota,   
    imprimir_nota   
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('', home, name='home'),
    path('emitir/', emitir, name='emitir'),
    path('notas/', listar_notas, name='listar_notas'),

    path('api/produtos/', buscar_produtos, name='buscar_produtos'),
    
    path('emitir-nota/', emitir_nota, name='emitir_nota'), 
    
    path('imprimir-nota/<int:nota_id>/', imprimir_nota, name='imprimir_nota'),
]