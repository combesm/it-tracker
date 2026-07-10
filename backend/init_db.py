import sqlite3
import os

DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'database.db'))
# S'assurer que le dossier parent de la base existe
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    try:
        os.makedirs(db_dir, exist_ok=True)
    except Exception as e:
        print(f"Impossible de créer le dossier de base de données {db_dir} : {e}")


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

    # Table Asset URLs (multi-sources)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS asset_urls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        url TEXT NOT NULL,
        is_primary INTEGER DEFAULT 0,
        FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
    );
    """)

    # Table Alerts (avec la colonne description, trigger_url et is_secondary)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        link TEXT,
        pub_date TEXT,
        resolved INTEGER DEFAULT 0,
        trigger_url TEXT,
        is_secondary INTEGER DEFAULT 0,
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
    assets = [
        ('Synology DSM', 'Synology', '7.2.1-69057', 'Self-hosted', 'NAS-PHY-01 (IP: 192.168.1.100)', 'Perpétuelle', None, 'https://www.cert.ssi.gouv.fr/feed/', 'MUC', 'Herakles'),
        ('Windows Server 2022', 'Microsoft', '21H2 (10.0.20348)', 'On-premise', None, 'Limitée', '2027-12-31', 'https://www.cert.ssi.gouv.fr/feed/', 'ALF', 'Hexatio, Oztyis'),
        ('Metabase', 'Metabase Core', '0.45.0', 'Self-hosted', 'VM-APP-02', 'Perpétuelle', None, 'https://github.com/metabase/metabase/releases.atom', 'JDO', 'Groupe, Herakles')
    ]
    cursor.executemany("""
    INSERT INTO assets (nom_produit, fournisseur, version_actuelle, type_deploiement, machine_hebergement, type_licence, date_expiration, url_rss, responsable, entites)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, assets)

    # Récupérer les IDs des actifs
    cursor.execute("SELECT id FROM assets WHERE nom_produit = 'Synology DSM';")
    synology_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM assets WHERE nom_produit = 'Windows Server 2022';")
    windows_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM assets WHERE nom_produit = 'Metabase';")
    metabase_id = cursor.fetchone()[0]

    # Insérer les URLs de test dans asset_urls
    cursor.execute("INSERT INTO asset_urls (asset_id, url, is_primary) VALUES (?, 'https://www.cert.ssi.gouv.fr/feed/', 1);", (synology_id,))
    cursor.execute("INSERT INTO asset_urls (asset_id, url, is_primary) VALUES (?, 'https://www.cert.ssi.gouv.fr/feed/', 1);", (windows_id,))
    cursor.execute("INSERT INTO asset_urls (asset_id, url, is_primary) VALUES (?, 'https://github.com/metabase/metabase/releases.atom', 1);", (metabase_id,))

    # Données d'alertes de test riches pour le filtrage
    alerts = [
        # Synology alerte 1 : Corrigé en 7.2.1-69057. Notre version est 7.2.1-69057. Cette alerte doit être MASQUÉE !
        (synology_id, "CERTFR-2026-AVI-0500 : Vulnérabilité dans Synology DSM", 
         "Une faille affecte Synology DSM. Versions impactées : 7.0.0-7.2.1-69056. Upgrade to version 7.2.1-69057 pour corriger.", 
         "https://www.cert.ssi.gouv.fr/avis/CERTFR-2026-AVI-0500/", "2026-07-08T10:00:00Z", 0, "https://www.cert.ssi.gouv.fr/feed/", 0),
        
        # Synology alerte 2 : Versions antérieures à 7.2.2-00000. Notre version est 7.2.1-69057. Cette alerte doit s'afficher en priorité HAUTE !
        (synology_id, "CERTFR-2026-AVI-0498 : Multiples vulnérabilités dans les produits Synology", 
         "Des failles critiques ont été identifiées. Affected Installs: versions antérieures à 7.2.2-00000.", 
         "https://www.cert.ssi.gouv.fr/avis/CERTFR-2026-AVI-0498/", "2026-07-07T14:30:00Z", 0, "https://www.cert.ssi.gouv.fr/feed/", 0),
        
        # Windows alerte 1 : Pas d'informations précises de version dans la description. Doit s'afficher en REPLI (Vérification manuelle).
        (windows_id, "CERTFR-2026-AVI-0480 : Vulnérabilités dans Microsoft Windows Server", 
         "Des vulnérabilités non spécifiées permettent l'exécution de code à distance sur les serveurs.", 
         "https://www.cert.ssi.gouv.fr/avis/CERTFR-2026-AVI-0480/", "2026-07-06T09:00:00Z", 0, "https://www.cert.ssi.gouv.fr/feed/", 0),

        # Metabase alerte 1 : Release v0.46.0. Notre version actuelle est 0.45.0. Doit s'afficher comme MISE À JOUR DISPONIBLE.
        (metabase_id, "v0.46.0", 
         "Nouvelle version corrective et fonctionnelle de Metabase.", 
         "https://github.com/metabase/metabase/releases/tag/v0.46.0", "2026-07-05T12:00:00Z", 0, "https://github.com/metabase/metabase/releases.atom", 0),

        # Metabase alerte 2 : Release v0.44.0. Notre version actuelle est 0.45.0. Cette alerte doit être MASQUÉE car nous sommes déjà en version supérieure !
        (metabase_id, "v0.44.0", 
         "Version obsolète de Metabase.", 
         "https://github.com/metabase/metabase/releases/tag/v0.44.0", "2026-07-04T12:00:00Z", 0, "https://github.com/metabase/metabase/releases.atom", 0)
    ]
    cursor.executemany("""
    INSERT INTO alerts (asset_id, title, description, link, pub_date, resolved, trigger_url, is_secondary)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, alerts)

    conn.commit()
    conn.close()
    print("Base de données initialisée avec succès.")

if __name__ == '__main__':
    init_db()
