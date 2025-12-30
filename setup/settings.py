from pathlib import Path
import os
import dj_database_url
from decouple import config

# ==================================================
# 1. CONFIGURAÇÕES DE DIRETÓRIOS
# ==================================================
# Define a pasta raiz do projeto (onde está o manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent

# ==================================================
# 2. SEGURANÇA E AMBIENTE
# ==================================================
# A SECRET_KEY deve ser mantida em sigilo e carregada via variável de ambiente
SECRET_KEY = config('SECRET_KEY', default='django-insecure-cn=0gd6kzc!x8)b3wj22sx-m0*%njdfc=^jq-rrz$lnvjr^nvl')

# DEBUG deve ser False em produção para evitar exposição de dados sensíveis
DEBUG = config('DEBUG', default=True, cast=bool)

# Define quais domínios podem acessar este servidor
ALLOWED_HOSTS = ['*']

# ==================================================
# 3. DEFINIÇÃO DA APLICAÇÃO
# ==================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Aplicações do projeto Mateco
    'core',
    'estoque',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Gerencia arquivos estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'setup.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Pasta global de HTMLs
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'setup.wsgi.application'

# ==================================================
# 4. BANCO DE DADOS
# ==================================================
# Padrão: SQLite para desenvolvimento local
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Se DATABASE_URL estiver presente (Produção/Vercel), utiliza PostgreSQL
if config('DATABASE_URL', default=None):
    DATABASES['default'] = dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True
    )

# ==================================================
# 5. INTERNACIONALIZAÇÃO (TRADUÇÃO E HORÁRIO)
# ==================================================
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True 

# ==================================================
# 6. ARQUIVOS ESTÁTICOS (CSS, JS, IMAGENS)
# ==================================================
STATIC_URL = '/static/'

# Pasta onde o Django agrupa arquivos para produção
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Pastas onde o Django procura arquivos estáticos em desenvolvimento
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Configuração do WhiteNoise para compressão de arquivos
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# ==================================================
# 7. AUTENTICAÇÃO E ACESSO
# ==================================================
LOGIN_REDIRECT_URL = 'home' # Após login, vai para a Home
LOGOUT_REDIRECT_URL = 'login' # Após logout, vai para o Login
LOGIN_URL = 'login' # URL da página de login