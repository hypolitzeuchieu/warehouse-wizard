#!/bin/sh

# Appliquer les migrations
echo "Appliquer les migrations..."
python manage.py migrate --noinput

# Lancer le serveur Django
echo "Démarrer le serveur Django..."
exec "$@"
