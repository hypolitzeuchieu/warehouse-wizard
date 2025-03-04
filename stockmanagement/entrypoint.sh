#!/bin/sh

# Attendre que la base de données soit prête
echo "Attente du serveur de base de données..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "Base de données prête."

# Appliquer les migrations
echo "Application des migrations..."
python manage.py migrate --noinput

# Lancer le serveur ou le worker en fonction de l'argument
if [ "$1" = 'worker' ]; then
    echo "Démarrage du worker Celery..."
    exec celery -A votre_projet worker --loglevel=info
else
    echo "Démarrage du serveur Django..."
    exec "$@"
fi
