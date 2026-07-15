# Herakles IT Tracker - Inventaire & Suivi des Vulnérabilités

Cette application Single Page (SPA) permet de suivre l'inventaire informatique (logiciels, OS, serveurs, licences) d'une PME et de surveiller en temps réel les vulnérabilités de sécurité associées grâce aux flux RSS de sécurité (CERT-FR et flux configurés par actif).

L'interface est conforme à la charte graphique Herakles (mode clair épuré, bleu corporate, sans émoji). Elle propose l'export Excel multi-onglets complet de toutes les données et gère l'historique des changements de version lors de la résolution d'alertes.

---

## 🐋 Méthode 1 : Déploiement avec Docker & Docker Compose (Recommandée)

Cette méthode est idéale pour la production ou la recette. Elle encapsule l'application dans un conteneur et gère automatiquement la persistance des données.

### Prérequis
- **Docker** installé sur votre machine.
- **Docker Compose** (souvent inclus avec Docker Desktop ou sous forme de plugin `docker-compose`).

### Étapes d'installation

1. **Cloner ou se positionner dans le répertoire du projet** :
   ```bash
   cd /home/rustdesk-host/IT-TRACKER
   ```

2. **Démarrer l'application avec Docker Compose** :
   ```bash
   docker compose up -d --build
   ```
   *Le drapeau `--build` force la compilation du frontend React et du serveur Flask lors du premier lancement. Le drapeau `-d` exécute le conteneur en arrière-plan.*

3. **Accéder à l'application** :
   Ouvrez votre navigateur web et rendez-vous sur :
   👉 **[http://localhost:5000](http://localhost:5000)**

### 💾 Persistance des données (Base de données SQLite)
Le fichier `docker-compose.yml` est configuré avec un **volume Docker bind-mount** :
```yaml
volumes:
  - ./data:/app/backend/data
```
- Lors du démarrage, Docker crée automatiquement un dossier `./data/` à la racine du projet sur la machine hôte.
- Le fichier SQLite de la base de données (`database.db`) y est stocké de manière persistante.
- **Sécurité** : Vous pouvez arrêter, supprimer, reconstruire ou mettre à jour le conteneur Docker à tout moment sans **jamais perdre vos données**. La base de données reste saine sur le disque dur de la machine hôte.

### Commandes utiles pour Docker

- **Arrêter l'application** :
  ```bash
  docker compose down
  ```
- **Consulter les logs en temps réel** :
  ```bash
  docker compose logs -f
  ```
- **Réinitialiser la base de données avec les données de test (jeu d'essai Herakles)** :
  ```bash
  docker compose exec it-tracker python backend/init_db.py
  ```

---

## 🔗 Intégration Native d'OpenCVE

L'application intègre un connecteur natif pour OpenCVE via son API REST. Cela évite d'avoir à gérer manuellement des fichiers ou des flux RSS de tierces parties.

### 1. Configurer les identifiants d'API
Ouvrez le fichier `docker-compose.yml` et configurez vos accès de connexion OpenCVE sous la section `environment` :
```yaml
environment:
  - OPENCVE_URL=http://host.docker.internal:8000
  - OPENCVE_USER=votre_utilisateur
  - OPENCVE_PASSWORD=votre_mot_de_passe
```
*(L'hôte `host.docker.internal` redirige automatiquement les requêtes vers l'IP de votre machine hôte/VM depuis le conteneur Docker).*

### 2. Configurer les URLs personnalisées dans IT-Tracker
Dans l'onglet **Actifs & Services**, créez ou modifiez un actif et saisissez une URL au format personnalisé suivant dans le champ **URL de flux RSS** :
- **Filtrer par vendeur (Vendor)** :
  `opencve://vendor/<nom_du_vendeur>` (ex: `opencve://vendor/joomla`)
- **Filtrer par produit (Product)** :
  `opencve://product/<nom_du_vendeur>/<nom_du_produit>` (ex: `opencve://product/rustdesk/rustdesk`)

Lors de la synchronisation, l'IT-Tracker interrogera automatiquement l'API locale d'OpenCVE pour récupérer les CVEs, extraire les versions vulnérables et appliquer son filtrage sémantique intelligent !

---

## 💻 Méthode 2 : Lancement en local (sans Docker)

Cette méthode est utile pour le développement.

### Prérequis
- **Python 3.12+**
- **Node.js 20+** et **npm**

### Étapes d'installation

1. **Compiler le frontend React** :
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```

2. **Initialiser la base de données de test SQLite** (si non existante) :
   ```bash
   source venv/bin/activate
   python backend/init_db.py
   ```

3. **Lancer l'application via le script de démarrage** :
   ```bash
   ./start.sh
   ```
   *Ce script active automatiquement l'environnement virtuel Python et démarre le serveur Flask sur [http://localhost:5000](http://localhost:5000).*

---

## 🛠️ Architecture Technique
- **Frontend** : React, Vite, Tailwind CSS v4, SheetJS (export Excel côté client).
- **Backend** : Python Flask, parseur RSS asynchrone, analyseur sémantique de versions (`packaging.version`), expressions régulières pour plages de vulnérabilités.
- **Base de données** : SQLite locale (`database.db`).
- **Logs de mise à jour** : Table SQL `update_logs` stockant l'évolution des versions de l'inventaire lors des résolutions.
