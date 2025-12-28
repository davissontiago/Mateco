#!/bin/bash
echo "Building the project..."
pip install -r requirements.txt
python3 manage.py collectstatic --noinput

# Cria a pasta public
mkdir -p public
# Cria um arquivo simples dentro dela para o Vercel validar o build
echo "Build Sucesso" > public/index.html