import csv
import os
from django.core.management.base import BaseCommand
from estoque.models import Produto

class Command(BaseCommand):
    help = 'Importa produtos de um arquivo CSV'

    def handle(self, *args, **kwargs):
        caminho_arquivo = 'Produtos.csv' # Nome do arquivo na raiz

        if not os.path.exists(caminho_arquivo):
            self.stdout.write(self.style.ERROR(f'Arquivo "{caminho_arquivo}" não encontrado!'))
            return

        with open(caminho_arquivo, mode='r', encoding='utf-8-sig') as arquivo:
            leitor = csv.DictReader(arquivo, delimiter=';')
            
            produtos_criados = 0
            produtos_atualizados = 0

            for linha in leitor:
                try:
                    # Limpa e prepara os dados
                    codigo = linha['Código de Barras'].strip().replace('"', '')
                    nome = linha['Descrição'].strip()
                    ncm = linha['NCM'].strip().replace('.', '') # Remove pontos do NCM se houver
                    
                    # Converte preço (troca vírgula por ponto se necessário)
                    preco_str = linha['Preço Venda Varejo'].replace(',', '.')
                    preco = float(preco_str) if preco_str else 0.0
                    
                    # Converte estoque
                    estoque_str = linha['Quantidade em Estoque'].replace(',', '.')
                    estoque = int(float(estoque_str)) if estoque_str else 0

                    # Tenta pegar um produto existente ou criar um novo
                    # update_or_create é mágico: se o código já existe, ele atualiza. Se não, cria.
                    obj, created = Produto.objects.update_or_create(
                        codigo=codigo,
                        defaults={
                            'nome': nome,
                            'preco': preco,
                            'ncm': ncm,
                            'estoque_atual': estoque
                        }
                    )

                    if created:
                        produtos_criados += 1
                    else:
                        produtos_atualizados += 1

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Erro ao importar item {linha.get("Descrição", "?")}: {e}'))

            self.stdout.write(self.style.SUCCESS(f'Importação concluída! Criados: {produtos_criados} | Atualizados: {produtos_atualizados}'))