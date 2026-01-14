from django import forms
from .models import Produto

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        # Define os campos que aparecerão no formulário
        fields = ['codigo', 'nome', 'ncm', 'preco', 'estoque_atual']
        
        # Define o visual dos campos (CSS do Bootstrap/Estilo)
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 001'}),
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Produto'}),
            'ncm': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NCM (8 dígitos)'}),
            'preco': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'estoque_atual': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
        }