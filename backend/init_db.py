import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def init_db():
    print(f"Initialisation de la base de données à : {DB_PATH}")
    # Supprimer l'ancienne base pour régénérer le schéma proprement
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print("Ancienne base de données supprimée.")
        except Exception as e:
            print(f"Avertissement lors de la suppression de l'ancienne base : {e}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Activation des clés étrangères
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Table Team
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS team (
        trigramme TEXT PRIMARY KEY,
        email TEXT NOT NULL
    );
    """)

    # Table Assets
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_produit TEXT NOT NULL,
        fournisseur TEXT,
        version_actuelle TEXT NOT NULL,
        type_deploiement TEXT NOT NULL,
        machine_hebergement TEXT,
        type_licence TEXT DEFAULT 'Perpétuelle',
        date_expiration TEXT,
        url_rss TEXT,
        responsable TEXT NOT NULL,
        entites TEXT NOT NULL DEFAULT 'Groupe',
        FOREIGN KEY(responsable) REFERENCES team(trigramme) ON DELETE RESTRICT
    );
    """)

    # Table Alerts
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        link TEXT,
        pub_date TEXT,
        resolved INTEGER DEFAULT 0,
        FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
    );
    """)

    # Insertion des données de test
    print("Insertion des données de test...")
    # Membres de l'équipe
    members = [
        ('MUC', 'm.dupont@herakles.com'),
        ('JDO', 'j.durand@herakles.com'),
        ('ALF', 'a.lefevre@herakles.com')
    ]
    cursor.executemany("INSERT INTO team (trigramme, email) VALUES (?, ?);", members)

    # Actifs & Services
    # Champs requis : nom_produit, version_actuelle, type_deploiement, responsable
    # Optionnels : fournisseur (nullable), type_licence (default Perpétuelle), date_expiration, url_rss, entites (default Groupe)
    assets = [
        ('Synology DSM', 'Synology', '7.2.1-69057', 'Self-hosted', 'NAS-PHY-01 (IP: 192.168.1.100)', 'Perpétuelle', None, 'https://www.cert.ssi.gouv.fr/feed/', 'MUC', 'Herakles'),
        ('Slack Enterprise Grid', None, 'Cloud', 'SaaS', None, 'Limitée', '2026-07-28', '', 'JDO', 'Groupe, Herakles, Oztyis'),
        ('Windows Server 2022', 'Microsoft', '21H2 (10.0.20348)', 'On-premise', None, 'Limitée', '2027-12-31', 'https://www.cert.ssi.gouv.fr/feed/', 'ALF', 'Hexatio, Oztyis')
    ]
    cursor.executemany("""
    INSERT INTO assets (nom_produit, fournisseur, version_actuelle, type_deploiement, machine_hebergement, type_licence, date_expiration, url_rss, responsable, entites)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, assets)

    # Quelques alertes par défaut pour démarrer
    cursor.execute("SELECT id FROM assets WHERE nom_produit = 'Synology DSM';")
    synology_id = cursor.fetchone()[0]
    alerts = [
        (synology_id, "CERTFR-2026-AVI-0500 : Vulnérabilité dans Synology DSM", "https://www.cert.ssi.gouv.fr/avis/CERTFR-2026-AVI-0500/", "2026-07-08T10:00:00Z", 0),
        (synology_id, "CERTFR-2026-AVI-0498 : Multiples vulnérabilités dans les produits Synology", "https://www.cert.ssi.gouv.fr/avis/CERTFR-2026-AVI-0498/", "2026-07-07T14:30:00Z", 0)
    ]
    cursor.executemany("""
    INSERT INTO alerts (asset_id, title, link, pub_date, resolved)
    VALUES (?, ?, ?, ?, ?);
    """, alerts)

    conn.commit()
    conn.close()
    print("Base de données initialisée avec succès.")

if __name__ == '__main__':
    init_db()
