import csv
import os
from django.core.management.base import BaseCommand
from estoque.models import Produto

class Command(BaseCommand):
    """
    Comando customizado para importar dados de produtos via arquivo CSV.
    
    O script lê o arquivo 'Produtos.csv' na raiz do projeto e realiza a 
    sincronização com o banco de dados utilizando a lógica de upsert 
    (atualiza se existir, cria se for novo).
    """

    help = 'Importa ou atualiza produtos a partir de um arquivo CSV (Produtos.csv)'

    def handle(self, *args, **kwargs):
        """Execução principal do comando de importação."""
        
        # Define o local do arquivo (esperado na raiz do diretório Mateco)
        caminho_arquivo = 'Produtos.csv' 

        # Verificação de segurança: interrompe se o arquivo não estiver presente
        if not os.path.exists(caminho_arquivo):
            self.stdout.write(self.style.ERROR(f'Arquivo "{caminho_arquivo}" não encontrado!'))
            return

        # Abre o arquivo com encoding 'utf-8-sig' para ignorar o BOM do Excel
        with open(caminho_arquivo, mode='r', encoding='utf-8-sig') as arquivo:
            # O delimitador ';' é o padrão para CSVs gerados no Brasil
            leitor = csv.DictReader(arquivo, delimiter=';')
            
            produtos_criados = 0
            produtos_atualizados = 0

            self.stdout.write('Iniciando processamento do CSV...')

            for linha in leitor:
                try:
                    # --- 1. Limpeza e Tratamento de Dados ---
                    # Remove aspas e espaços extras do código de barras
                    codigo = linha['Código de Barras'].strip().replace('"', '')
                    nome = linha['Descrição'].strip()
                    # Remove pontos do NCM para manter apenas os números
                    ncm = linha['NCM'].strip().replace('.', '') 
                    
                    # Converte preço: substitui vírgula decimal brasileira por ponto
                    preco_str = linha['Preço Venda Varejo'].replace(',', '.')
                    preco = float(preco_str) if preco_str else 0.0
                    
                    # Converte estoque: trata possíveis floats vindo do CSV para inteiro
                    estoque_str = linha['Quantidade em Estoque'].replace(',', '.')
                    estoque = int(float(estoque_str)) if estoque_str else 0

                    # --- 2. Sincronização com Banco de Dados ---
                    # A lógica de 'update_or_create' usa o código como chave única
                    obj, created = Produto.objects.update_or_create(
                        codigo=codigo,
                        defaults={
                            'nome': nome,
                            'preco': preco,
                            'ncm': ncm,
                            'estoque_atual': estoque
                        }
                    )

                    # Contabiliza os resultados para o relatório final
                    if created:
                        produtos_criados += 1
                    else:
                        produtos_atualizados += 1

                except Exception as e:
                    # Em caso de erro em uma linha, o script avisa e continua para a próxima
                    self.stdout.write(
                        self.style.WARNING(f'Erro no item {linha.get("Descrição", "?")}: {e}')
                    )

            # Relatório final de execução no terminal
            self.stdout.write(
                self.style.SUCCESS(
                    f'Importação concluída! '
                    f'Criados: {produtos_criados} | '
                    f'Atualizados: {produtos_atualizados}'
                )
            )