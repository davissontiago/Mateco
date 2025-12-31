from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import NotaFiscal, Empresa, PerfilUsuario

# ==================================================
# 1. ADMINISTRAÇÃO DE EMPRESAS
# ==================================================
@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnpj', 'cidade', 'uf', 'crt')
    search_fields = ('nome', 'cnpj')
    fieldsets = (
        ('Identificação', {
            'fields': ('nome', 'cnpj', 'inscricao_estadual', 'crt')
        }),
        ('Endereço', {
            'fields': ('cep', 'logradouro', 'numero', 'bairro', 'cidade', 'uf')
        }),
        ('Integração Nuvem Fiscal', {
            'fields': ('nuvem_client_id', 'nuvem_client_secret'),
            'description': 'Credenciais geradas no painel da Nuvem Fiscal.'
        }),
    )

# ==================================================
# 2. VÍNCULO USUÁRIO -> EMPRESA (INLINE)
# ==================================================
# Isso faz aparecer o campo "Empresa" dentro da tela de Usuários
class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Empresa Associada'

# Estendendo o UserAdmin padrão do Django
class CustomUserAdmin(UserAdmin):
    inlines = (PerfilUsuarioInline, )

# Remove o registro antigo de User e adiciona o nosso personalizado
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# ==================================================
# 3. ADMINISTRAÇÃO DE NOTAS
# ==================================================
@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display = ('numero', 'data_emissao', 'valor_total', 'status')
    list_filter = ('status', 'data_emissao')
    search_fields = ('numero', 'chave')