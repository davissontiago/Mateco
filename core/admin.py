from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import NotaFiscal, Empresa, PerfilUsuario, Cliente

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
    
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf_cnpj', 'telefone', 'cidade', 'empresa')
    list_filter = ('empresa', 'uf')
    search_fields = ('nome', 'cpf_cnpj', 'email')
    
    # 1. BLINDAGEM: Só mostra clientes da empresa do usuário
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        try:
            return qs.filter(empresa=request.user.perfil.empresa)
        except:
            return qs.none()

    # 2. AUTOMAÇÃO: Salva a empresa automaticamente ao criar cliente
    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.empresa = request.user.perfil.empresa
        super().save_model(request, obj, form, change)

    # 3. INTERFACE: Esconde o campo 'empresa' para usuários comuns
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            if 'empresa' in form.base_fields:
                form.base_fields['empresa'].widget.attrs['disabled'] = True
                form.base_fields['empresa'].required = False
        return form

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