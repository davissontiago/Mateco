from django.apps import AppConfig

class EstoqueConfig(AppConfig):
    """
    Configuração da aplicação 'estoque'.
    
    Esta aplicação é responsável pelo gerenciamento do catálogo de produtos,
    controle de níveis de inventário e processos de importação de dados via CSV.
    """

    # Define o nome interno da aplicação dentro do projeto Django
    name = 'estoque'
    
    # Define o tipo de campo de auto-incremento padrão para os modelos desta aplicação
    # O BigAutoField é o recomendado para evitar limites de ID em grandes inventários
    default_auto_field = 'django.db.models.BigAutoField'
    
    # Define o nome amigável que aparecerá no cabeçalho do Painel Administrativo
    verbose_name = 'Gestão de Inventário e Produtos'