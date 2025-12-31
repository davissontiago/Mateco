from django import forms
from .models import Cliente

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        # Não incluímos 'empresa' aqui, pois será preenchida automaticamente no backend
        fields = ['nome', 'cpf_cnpj', 'email', 'telefone', 'cep', 'endereco', 'numero', 'bairro', 'cidade', 'uf']
        
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome Completo ou Razão Social'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apenas números'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(XX) 9XXXX-XXXX'}),
            'cidade': forms.TextInput(attrs={'class': 'form-control'}),
            'uf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'MA'}),
        }