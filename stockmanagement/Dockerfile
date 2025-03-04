# Utiliser l'image Python comme base
FROM python:3.11.5-bookworm AS builder

# Définir le répertoire de travail
WORKDIR /app

# Mettre à jour les dépôts et installer netcat-openbsd
RUN apt-get update && apt-get install -y netcat-openbsd && apt-get clean

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY . .

# Exposer le port 8000
EXPOSE 8000

# Copier le script d'entrée et le rendre exécutable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Définir le point d'entrée
ENTRYPOINT ["/app/entrypoint.sh"]

# Commande par défaut
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
