#!/bin/bash
echo "Building the project..."
pip install -r requirements.txt
python3 manage.py collectstatic --noinput

# Cria uma pasta vazia apenas para o Vercel não dar erro
mkdir -p public