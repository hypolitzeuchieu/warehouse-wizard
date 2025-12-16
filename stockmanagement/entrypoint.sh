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
    exec celery -A retailpulse worker --loglevel=info
elif [ "$1" = 'beat' ]; then
    echo "Démarrage de Celery Beat..."
    exec celery -A retailpulse beat --loglevel=info
else
    # Si aucune commande spécifique n'est fournie, utiliser gunicorn pour la production
    if [ -z "$1" ]; then
        echo "Démarrage du serveur Django avec Gunicorn..."
        exec gunicorn retailpulse.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120
    else
        echo "Démarrage avec la commande fournie..."
        exec "$@"
    fi
fi
