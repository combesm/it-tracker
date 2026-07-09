#!/bin/bash
# Script de démarrage de l'application IT-TRACKER (Herakles)

# Obtenir le répertoire racine du script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "   Démarrage de l'Inventaire IT & Suivi des Vulnérabilités"
echo "=========================================================="
echo ""

# Activation de l'environnement virtuel Python
if [ -d "venv" ]; then
    echo "Activation de l'environnement virtuel Python (venv)..."
    source venv/bin/activate
else
    echo "Erreur : L'environnement virtuel 'venv' n'existe pas."
    exit 1
fi

# Démarrage de l'application Flask (sert aussi l'interface React compilée)
echo "Lancement du serveur backend Flask sur le port 5000..."
echo "Accédez à l'application via : http://localhost:5000"
echo ""

python3 backend/app.py
