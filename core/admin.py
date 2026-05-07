from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import NotaFiscal, Empresa, PerfilUsuario, Cliente


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnpj', 'cidade', 'ambiente', 'emissor_fiscal', '_cert_hom', '_cert_prod')

    def _cert_hom(self, obj):
        if obj.certificado_a1_pfx_homologacao:
            val = obj.certificado_a1_validade_homologacao
            return f"✅ {val}" if val else "✅ configurado"
        return "—"
    _cert_hom.short_description = "Cert. Homolog."

    def _cert_prod(self, obj):
        if obj.certificado_a1_pfx_producao:
            val = obj.certificado_a1_validade_producao
            return f"✅ {val}" if val else "✅ configurado"
        return "—"
    _cert_prod.short_description = "Cert. Produção"

    fieldsets = (
        ('Identificação', {
            'fields': ('nome', 'nome_fantasia', 'cnpj', 'inscricao_estadual', 'crt')
        }),
        ('Configuração do Sistema', {
            'fields': ('ambiente', 'emissor_fiscal', 'cor_primaria', 'cor_secundaria')
        }),
        ('Endereço', {
            'fields': ('cep', 'logradouro', 'numero', 'bairro', 'cidade', 'uf', 'cod_municipio')
        }),
        ('Nuvem Fiscal — Homologação', {
            'classes': ('collapse',),
            'fields': ('nuvem_client_id_homologacao', 'nuvem_client_secret_homologacao'),
        }),
        ('Nuvem Fiscal — Produção', {
            'classes': ('collapse',),
            'fields': ('nuvem_client_id_producao', 'nuvem_client_secret_producao'),
        }),
        ('Certificado A1 — Homologação (somente leitura aqui)', {
            'classes': ('collapse',),
            'description': 'Use /configuracoes/ para enviar o PFX. Aqui só exibe metadados.',
            'fields': ('certificado_a1_validade_homologacao',),
        }),
        ('Certificado A1 — Produção (somente leitura aqui)', {
            'classes': ('collapse',),
            'description': 'Use /configuracoes/ para enviar o PFX. Aqui só exibe metadados.',
            'fields': ('certificado_a1_validade_producao',),
        }),
        ('CSC — QR Code NFC-e', {
            'classes': ('collapse',),
            'fields': ('csc_id_homologacao', 'csc_id_producao'),
        }),
        ('Séries NFC-e', {
            'fields': ('serie_nfce_homologacao', 'serie_nfce_producao'),
        }),
    )

    # Impede edição dos BinaryFields cifrados via admin (dados sensíveis)
    readonly_fields = (
        'certificado_a1_validade_homologacao',
        'certificado_a1_validade_producao',
    )

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        # Remove campos BinaryField cifrados — nunca exibir no admin
        binarios = {
            'certificado_a1_pfx_homologacao', 'certificado_a1_senha_homologacao',
            'certificado_a1_pfx_producao', 'certificado_a1_senha_producao',
            'csc_token_homologacao', 'csc_token_producao',
        }
        return [f for f in fields if f not in binarios]


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf_cnpj', 'telefone', 'cidade', 'empresa')
    list_filter = ('empresa', 'uf')
    search_fields = ('nome', 'cpf_cnpj', 'email')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        try:
            return qs.filter(empresa=request.user.perfil.empresa)
        except Exception:
            return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.empresa = request.user.perfil.empresa
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and 'empresa' in form.base_fields:
            form.base_fields['empresa'].widget.attrs['disabled'] = True
            form.base_fields['empresa'].required = False
        return form


class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Empresa Associada'


class CustomUserAdmin(UserAdmin):
    inlines = (PerfilUsuarioInline,)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display = ('numero', 'serie', 'ambiente', 'data_emissao', 'valor_total', 'status', 'protocolo_autorizacao')
    list_filter = ('ambiente', 'serie', 'status', 'data_emissao')
    search_fields = ('numero', 'cliente__nome', 'chave', 'protocolo_autorizacao')
    readonly_fields = ('xml_assinado', 'xml_cancelamento', 'protocolo_autorizacao', 'protocolo_cancelamento',
                       'qrcode_url', 'data_cancelamento')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        try:
            return qs.filter(empresa=request.user.perfil.empresa)
        except Exception:
            return qs.none()
