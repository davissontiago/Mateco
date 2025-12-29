import os
from pathlib import Path
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise

# Configurações padrão do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')

# Inicializa a aplicação Django
application = get_wsgi_application()

# --- CORREÇÃO PARA O VERCEL ---
# Define o caminho base (Raiz do projeto)
BASE_DIR = Path(__file__).resolve().parent.parent

# Define onde estão os arquivos estáticos coletados (staticfiles na raiz)
STATIC_ROOT = BASE_DIR / 'staticfiles'

# "Envelopa" a aplicação com o WhiteNoise forçando o caminho correto
# Isso garante que o WhiteNoise sirva os arquivos independente do Middleware do settings
application = WhiteNoise(application, root=STATIC_ROOT)

# Variável para o Vercel encontrar a app
app = application