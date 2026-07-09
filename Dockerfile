# --- Etape 1 : Build du Frontend React ---
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Etape 2 : Image finale avec Flask ---
FROM python:3.12-slim
WORKDIR /app

# Dépendances système minimales pour SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copier et installer les dépendances Python
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copier le backend et les fichiers du frontend compilés
COPY backend/ ./backend/
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Créer un dossier dédié pour la base de données SQLite (pour le volume de persistance)
RUN mkdir -p /app/backend/data

# Configurer les variables d'environnement par défaut
ENV DB_PATH=/app/backend/data/database.db
ENV FLASK_APP=backend/app.py

EXPOSE 5000
CMD ["python", "backend/app.py"]
