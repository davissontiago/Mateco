from django.apps import AppConfig

class CoreConfig(AppConfig):
    """
    Configuração da aplicação 'core'.
    
    Esta é a aplicação principal do sistema Mateco, responsável pela
    gestão de notas fiscais, autenticação e a página inicial (Home).
    """

    # Define o nome interno da aplicação
    name = 'core'
    
    # Define o tipo de campo de auto-incremento padrão para os modelos
    default_auto_field = 'django.db.models.BigAutoField'
    
    # Define o nome amigável que aparecerá no painel administrativo
    verbose_name = 'Gestão Principal (Notas e Home)'