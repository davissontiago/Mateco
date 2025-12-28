#!/bin/bash
echo "Building the project..."
pip install -r requirements.txt
python3 manage.py collectstatic --noinput

# Cria a pasta public
mkdir -p public

# Cria um arquivo qualquer (QUE NÃO SEJA index.html) para o Vercel não reclamar que a pasta está vazia
echo "Build Check" > public/build_check.txt