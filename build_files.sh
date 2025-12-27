#!/bin/bash
echo "Building the project..."
pip install -r requirements.txt
python3 manage.py collectstatic --noinput