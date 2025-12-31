# Arquivo: core/context_processors.py

def empresa_atual_context(request):
    """
    Disponibiliza a variável {{ empresa_ativa }} em todos os templates HTML.
    Contém o objeto Empresa vinculado ao usuário logado.
    """
    contexto = {'empresa_ativa': None}

    if request.user.is_authenticated:
        try:
            # Tenta pegar a empresa através do perfil do usuário
            # O 'perfil' é o related_name que definimos no models.py
            perfil = getattr(request.user, 'perfil', None)
            if perfil:
                contexto['empresa_ativa'] = perfil.empresa
        except Exception as e:
            print(f"Erro no Context Processor: {e}")
            pass
            
    return contexto