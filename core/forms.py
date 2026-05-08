from cryptography.hazmat.primitives.serialization import pkcs12
from django import forms
from django.core.exceptions import ValidationError

from .models import Cliente, Empresa
from .crypto import encrypt_bytes, encrypt_str


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome', 'apelido', 'cpf_cnpj', 'email', 'telefone', 'cep', 'endereco', 'numero', 'bairro', 'cidade', 'cod_municipio', 'uf']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome Completo ou Razão Social'}),
            'apelido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome Curto (Ex: Mercadinho)'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apenas números'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(XX) 9XXXX-XXXX'}),
            'cidade': forms.TextInput(attrs={'class': 'form-control'}),
            'cod_municipio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 2103000 de Timon-MA'}),
            'uf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'MA'}),
        }


# ==============================================================
# FORMULÁRIO DE CONFIGURAÇÕES DA EMPRESA (FISCAL)
# ==============================================================

_FC = {'class': 'form-control'}
_SECRET = {'class': 'form-control', 'placeholder': '••••••••', 'autocomplete': 'off'}


class EmpresaConfigForm(forms.ModelForm):
    """
    Formulário para a página /configuracoes/.
    Gerencia emissor, ambiente, credenciais NuvemFiscal, certificado A1 e CSC.

    Campos BinaryField (certificado, senha, CSC token) não são exibidos diretamente;
    em vez disso, há campos extras de upload/input que são processados no save().
    """

    # --- Upload de certificado A1 (opcional; se não enviado, mantém o atual) ---
    pfx_homologacao = forms.FileField(required=False, label="Certificado .pfx Homologação",
                                      widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pfx,.p12'}))
    senha_pfx_homologacao = forms.CharField(required=False, label="Senha do PFX Homologação",
                                            widget=forms.PasswordInput(attrs=_SECRET, render_value=False))

    pfx_producao = forms.FileField(required=False, label="Certificado .pfx Produção",
                                   widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pfx,.p12'}))
    senha_pfx_producao = forms.CharField(required=False, label="Senha do PFX Produção",
                                         widget=forms.PasswordInput(attrs=_SECRET, render_value=False))

    # --- CSC tokens (plain text; cifrado no save()) ---
    csc_token_homologacao_plain = forms.CharField(required=False, label="CSC Token Homologação",
                                                  widget=forms.PasswordInput(attrs=_SECRET, render_value=False))
    csc_token_producao_plain = forms.CharField(required=False, label="CSC Token Produção",
                                               widget=forms.PasswordInput(attrs=_SECRET, render_value=False))

    class Meta:
        model = Empresa
        fields = [
            'ambiente', 'emissor_fiscal',
            'nuvem_client_id_homologacao', 'nuvem_client_secret_homologacao',
            'nuvem_client_id_producao', 'nuvem_client_secret_producao',
            'csc_id_homologacao', 'csc_id_producao',
            'serie_nfce_homologacao', 'serie_nfce_producao',
            'numero_nfce_homologacao', 'numero_nfce_producao',
        ]
        widgets = {
            'ambiente': forms.Select(attrs=_FC),
            'emissor_fiscal': forms.Select(attrs=_FC),
            'nuvem_client_id_homologacao': forms.TextInput(attrs=_FC),
            'nuvem_client_secret_homologacao': forms.PasswordInput(attrs=_SECRET, render_value=False),
            'nuvem_client_id_producao': forms.TextInput(attrs=_FC),
            'nuvem_client_secret_producao': forms.PasswordInput(attrs=_SECRET, render_value=False),
            'csc_id_homologacao': forms.TextInput(attrs={**_FC, 'placeholder': 'Ex: 1'}),
            'csc_id_producao': forms.TextInput(attrs={**_FC, 'placeholder': 'Ex: 1'}),
            'serie_nfce_homologacao': forms.NumberInput(attrs=_FC),
            'serie_nfce_producao': forms.NumberInput(attrs=_FC),
            'numero_nfce_homologacao': forms.NumberInput(attrs=_FC),
            'numero_nfce_producao': forms.NumberInput(attrs=_FC),
        }

    def _validar_pfx(self, pfx_file, senha):
        """Tenta abrir o PFX com a senha; levanta ValidationError se inválido."""
        if not pfx_file:
            return
        conteudo = pfx_file.read()
        pfx_file.seek(0)
        try:
            pkcs12.load_key_and_certificates(conteudo, (senha or '').encode('utf-8'))
        except Exception:
            raise ValidationError("Certificado PFX inválido ou senha incorreta.")

    def clean(self):
        cleaned = super().clean()

        # Valida PFX homologação se enviado
        pfx_hom = cleaned.get('pfx_homologacao')
        senha_hom = cleaned.get('senha_pfx_homologacao', '')
        if pfx_hom:
            self._validar_pfx(pfx_hom, senha_hom)

        # Valida PFX produção se enviado
        pfx_prod = cleaned.get('pfx_producao')
        senha_prod = cleaned.get('senha_pfx_producao', '')
        if pfx_prod:
            self._validar_pfx(pfx_prod, senha_prod)

        # Exige senha ao enviar um novo PFX
        if pfx_hom and not senha_hom:
            self.add_error('senha_pfx_homologacao', 'Informe a senha do certificado de homologação.')
        if pfx_prod and not senha_prod:
            self.add_error('senha_pfx_producao', 'Informe a senha do certificado de produção.')

        return cleaned

    def _extrair_validade(self, pfx_bytes, senha):
        """Retorna a data de expiração do certificado como date, ou None."""
        try:
            _, cert, _ = pkcs12.load_key_and_certificates(pfx_bytes, (senha or '').encode('utf-8'))
            if cert:
                return cert.not_valid_after_utc.date()
        except Exception:
            pass
        return None

    def save(self, commit=True):
        empresa = super().save(commit=False)

        # --- Certificado homologação ---
        pfx_hom = self.cleaned_data.get('pfx_homologacao')
        senha_hom = self.cleaned_data.get('senha_pfx_homologacao', '')
        if pfx_hom:
            pfx_bytes = pfx_hom.read()
            empresa.certificado_a1_pfx_homologacao = encrypt_bytes(pfx_bytes)
            empresa.certificado_a1_senha_homologacao = encrypt_str(senha_hom)
            empresa.certificado_a1_validade_homologacao = self._extrair_validade(pfx_bytes, senha_hom)

        # --- Certificado produção ---
        pfx_prod = self.cleaned_data.get('pfx_producao')
        senha_prod = self.cleaned_data.get('senha_pfx_producao', '')
        if pfx_prod:
            pfx_bytes = pfx_prod.read()
            empresa.certificado_a1_pfx_producao = encrypt_bytes(pfx_bytes)
            empresa.certificado_a1_senha_producao = encrypt_str(senha_prod)
            empresa.certificado_a1_validade_producao = self._extrair_validade(pfx_bytes, senha_prod)

        # --- CSC tokens ---
        token_hom = self.cleaned_data.get('csc_token_homologacao_plain', '')
        if token_hom:
            empresa.csc_token_homologacao = encrypt_str(token_hom)

        token_prod = self.cleaned_data.get('csc_token_producao_plain', '')
        if token_prod:
            empresa.csc_token_producao = encrypt_str(token_prod)

        if commit:
            empresa.save()
        return empresa
