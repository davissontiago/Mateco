import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')

application = get_wsgi_application()

# Executa migrations pendentes automaticamente no cold start (Vercel serverless).
try:
    from django.core.management import call_command
    call_command('migrate', '--no-input', verbosity=0)
except Exception:
    pass

app = application