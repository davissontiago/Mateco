import csv
import os
from django.core.management.base import BaseCommand
from estoque.models import Produto
from core.models import Empresa

class Command(BaseCommand):
    """
    Comando para importar produtos vinculando-os a uma Empresa específica.
    
    Uso:
        python manage.py importar_csv <id_empresa> --arquivo <nome_arquivo.csv>
    """
    help = 'Importa produtos de um CSV para uma Empresa específica.'

    def add_arguments(self, parser):
        # Argumento obrigatório: ID da empresa no banco
        parser.add_argument('empresa_id', type=int, help='ID da empresa para vincular os produtos')
        
        # Argumento opcional: Nome do arquivo (padrão: Produtos.csv)
        parser.add_argument(
            '--arquivo',
            type=str,
            default='Produtos.csv',
            help='Nome do arquivo CSV na raiz do projeto (Padrão: Produtos.csv)'
        )

    def handle(self, *args, **kwargs):
        empresa_id = kwargs['empresa_id']
        caminho_arquivo = kwargs['arquivo']

        # 1. Verifica se a empresa existe
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            self.stdout.write(self.style.SUCCESS(f'Importando para a empresa: {empresa.nome} (ID: {empresa.id})'))
        except Empresa.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Empresa com ID {empresa_id} não encontrada!'))
            return

        # 2. Verifica se o arquivo existe
        if not os.path.exists(caminho_arquivo):
            self.stdout.write(self.style.ERROR(f'Arquivo "{caminho_arquivo}" não encontrado!'))
            return

        # 3. Processamento
        with open(caminho_arquivo, mode='r', encoding='utf-8-sig') as arquivo:
            leitor = csv.DictReader(arquivo, delimiter=';')
            
            criados = 0
            atualizados = 0

            self.stdout.write('Iniciando processamento...')

            for linha in leitor:
                try:
                    # Tratamento de dados
                    codigo = linha['Código de Barras'].strip().replace('"', '')
                    nome = linha['Descrição'].strip()
                    ncm = linha['NCM'].strip().replace('.', '')
                    
                    preco_str = linha['Preço Venda Varejo'].replace(',', '.')
                    preco = float(preco_str) if preco_str else 0.0
                    
                    estoque_str = linha['Quantidade em Estoque'].replace(',', '.')
                    estoque = int(float(estoque_str)) if estoque_str else 0

                    # UPSERT com filtro de Empresa
                    # Agora usamos 'empresa' E 'codigo' para identificar o produto único
                    obj, created = Produto.objects.update_or_create(
                        empresa=empresa,  # <--- VÍNCULO OBRIGATÓRIO
                        codigo=codigo,
                        defaults={
                            'nome': nome,
                            'preco': preco,
                            'ncm': ncm,
                            'estoque_atual': estoque
                        }
                    )

                    if created:
                        criados += 1
                    else:
                        atualizados += 1

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Erro no item {linha.get("Descrição", "?")}: {e}'))

            self.stdout.write(self.style.SUCCESS(
                f'Concluído! Importados para {empresa.nome}: {criados} novos | {atualizados} atualizados'
            ))