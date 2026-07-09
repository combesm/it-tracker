from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, date
import re
from packaging.version import Version, InvalidVersion

def parse_version_safe(v_str):
    if not v_str:
        return None
    v_clean = v_str.strip()
    if v_clean.lower().startswith('v'):
        v_clean = v_clean[1:]
    try:
        return Version(v_clean)
    except InvalidVersion:
        return None

def analyze_alert(alert):
    title = alert.get('title') or ''
    description = alert.get('description') or ''
    version_actuelle = alert.get('version_actuelle') or ''
    
    # 1. Flux de Releases (ex: GitHub releases)
    # Le titre contient uniquement la version (ex: "v0.62.4" ou "0.62.4")
    version_pattern = r'^v?\d+(?:\.\d+)+(?:-\d+)?$'
    clean_title = title.strip()
    
    is_release_feed = bool(re.match(version_pattern, clean_title, re.IGNORECASE))
    
    if is_release_feed:
        rss_ver = parse_version_safe(clean_title)
        asset_ver = parse_version_safe(version_actuelle)
        
        if rss_ver is None:
            return 'show', 'manual_check', 'Vérification manuelle de la version requise', 'Non déterminée'
            
        if asset_ver is None:
            return 'show', 'manual_check', 'Vérification manuelle de la version requise', clean_title
            
        if rss_ver <= asset_ver:
            return 'hide', None, None, None
        else:
            return 'show', 'update_available', 'Mise à jour disponible', clean_title
            
    # 2. Flux de Sécurité textuels (ex: Joomla, CERT-FR)
    full_text = f"{title} \n {description}"
    asset_ver = parse_version_safe(version_actuelle)
    
    if asset_ver is None:
        return 'show', 'manual_check', 'Vérification manuelle de la version requise', 'Non déterminée'
        
    # Recherche d'indices de correctifs ou de versions saines
    correction_patterns = [
        r'(?:upgrade|update|corrige|fix|patch)\s+(?:to|in|à|dans)?\s*(?:version|v)?\s*(\d+\.\d+\.\d+(?:\.\d+)?)',
        r'fixed\s+in\s*(?:version|v)?\s*(\d+\.\d+\.\d+(?:\.\d+)?)',
        r'corrigé\s+dans\s+la\s+version\s*(\d+\.\d+\.\d+(?:\.\d+)?)'
    ]
    
    for pat in correction_patterns:
        match = re.search(pat, full_text, re.IGNORECASE)
        if match:
            fixed_ver_str = match.group(1)
            fixed_ver = parse_version_safe(fixed_ver_str)
            if fixed_ver and asset_ver >= fixed_ver:
                return 'hide', None, None, None

    # Recherche de plages de versions vulnérables
    range_patterns = [
        r'(?:versions?:?\s*)?(\d+\.\d+\.\d+(?:\.\d+)?)\s*(?:-|through|à|to)\s*(\d+\.\d+\.\d+(?:\.\d+)?)',
        r'versions?\s*(?:impactees|impactées)?\s*:?\s*(\d+\.\d+\.\d+(?:\.\d+)?)\s*-\s*(\d+\.\d+\.\d+(?:\.\d+)?)'
    ]
    
    for pat in range_patterns:
        match = re.search(pat, full_text, re.IGNORECASE)
        if match:
            start_str, end_str = match.group(1), match.group(2)
            start_ver = parse_version_safe(start_str)
            end_ver = parse_version_safe(end_str)
            
            if start_ver and end_ver:
                if start_ver <= asset_ver <= end_ver:
                    return 'show', 'high', 'Actif vulnérable (impacté)', f"{start_str} - {end_str}"
                else:
                    return 'hide', None, None, None

    # Recherche de versions antérieures vulnérables
    before_patterns = [
        r'versions?\s*(?:anterieures|antérieures|avant|before|prior\s+to)\s*(?:a|à)?\s*(?:version|v)?\s*(\d+\.\d+\.\d+(?:\.\d+)?)',
        r'versions?\s*<\s*(\d+\.\d+\.\d+(?:\.\d+)?)'
    ]
    
    for pat in before_patterns:
        match = re.search(pat, full_text, re.IGNORECASE)
        if match:
            limit_str = match.group(1)
            limit_ver = parse_version_safe(limit_str)
            if limit_ver:
                if asset_ver < limit_ver:
                    return 'show', 'high', 'Actif vulnérable (inférieur)', f"< {limit_str}"
                else:
                    return 'hide', None, None, None

    # Si aucune correspondance n'est trouvée -> Fallback (vérification manuelle)
    return 'show', 'manual_check', 'Vérification manuelle de la version requise', 'Non déterminée'

app = Flask(__name__, static_folder='../frontend/dist', static_url_path='/')
CORS(app) # Permet le cross-origin en développement

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')
CERT_FR_FEED_URL = "https://www.cert.ssi.gouv.fr/feed/"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# Helper: Parseur RSS générique et robuste
def fetch_rss_feed(url):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) herakles-it-tracker/1.0'}
        )
        # Timeout de 4 secondes pour éviter de bloquer l'application
        with urllib.request.urlopen(req, timeout=4) as response:
            xml_data = response.read()
        
        root = ET.fromstring(xml_data)
        
        items = []
        # Support d'une recherche générique d'éléments (ignorant les espaces de noms XML)
        def get_clean_tag(elem):
            return elem.tag.split('}')[-1]
            
        def find_child(elem, tag_name):
            for child in elem:
                if get_clean_tag(child) == tag_name:
                    return child
            return None
            
        all_items = []
        def search_items(elem):
            tag = get_clean_tag(elem)
            if tag in ('item', 'entry'):
                all_items.append(elem)
                return
            for child in elem:
                search_items(child)
                
        search_items(root)
        
        for item_elem in all_items:
            title_elem = find_child(item_elem, 'title')
            link_elem = find_child(item_elem, 'link')
            
            link_text = ""
            if link_elem is not None:
                if 'href' in link_elem.attrib:
                    link_text = link_elem.attrib['href']
                else:
                    link_text = link_elem.text or ""
            
            pub_date_elem = find_child(item_elem, 'pubDate')
            if pub_date_elem is None:
                pub_date_elem = find_child(item_elem, 'updated')
            if pub_date_elem is None:
                pub_date_elem = find_child(item_elem, 'published')
            
            # Extraction de description / summary / content
            desc_elem = find_child(item_elem, 'description')
            if desc_elem is None:
                desc_elem = find_child(item_elem, 'summary')
            if desc_elem is None:
                desc_elem = find_child(item_elem, 'content')
            
            title_text = title_elem.text if title_elem is not None else "Sans titre"
            pub_date_text = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text is not None else ""
            desc_text = desc_elem.text if desc_elem is not None and desc_elem.text is not None else ""
            
            items.append({
                'title': title_text,
                'link': link_text,
                'pub_date': pub_date_text,
                'description': desc_text
            })
        return items
    except Exception as e:
        print(f"Erreur de récupération du flux RSS ({url}): {e}")
        return None

# Endpoints API

# 1. Gestion de l'Équipe
@app.route('/api/team', methods=['GET'])
def get_team():
    conn = get_db_connection()
    members = conn.execute("SELECT * FROM team ORDER BY trigramme ASC;").fetchall()
    conn.close()
    return jsonify([dict(m) for m in members])

@app.route('/api/team', methods=['POST'])
def add_team_member():
    data = request.json
    trigramme = data.get('trigramme', '').strip().upper()
    email = data.get('email', '').strip()
    
    if not trigramme or not email:
        return jsonify({'error': 'Le trigramme et l\'adresse email sont requis.'}), 400
        
    if len(trigramme) != 3:
        return jsonify({'error': 'Le trigramme doit comporter exactement 3 caractères.'}), 400

    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO team (trigramme, email) VALUES (?, ?);", (trigramme, email))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': f'Le membre d\'équipe avec le trigramme {trigramme} existe déjà.'}), 400
    
    conn.close()
    return jsonify({'trigramme': trigramme, 'email': email}), 201

@app.route('/api/team/<trigramme>', methods=['DELETE'])
def delete_team_member(trigramme):
    trigramme = trigramme.upper()
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM team WHERE trigramme = ?;", (trigramme,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Impossible de supprimer ce responsable car il est associé à un ou plusieurs actifs.'}), 400
    conn.close()
    return jsonify({'success': True})

# 2. Gestion des Actifs
@app.route('/api/assets', methods=['GET'])
def get_assets():
    conn = get_db_connection()
    # Récupère les détails avec l'email du responsable
    assets = conn.execute("""
        SELECT a.*, t.email as email_responsable 
        FROM assets a
        JOIN team t ON a.responsable = t.trigramme
        ORDER BY a.nom_produit ASC;
    """).fetchall()
    conn.close()
    return jsonify([dict(a) for a in assets])

@app.route('/api/assets', methods=['POST'])
def add_asset():
    data = request.json
    nom_produit = (data.get('nom_produit') or '').strip()
    fournisseur = (data.get('fournisseur') or '').strip() or None
    version_actuelle = (data.get('version_actuelle') or '').strip()
    type_deploiement = data.get('type_deploiement') or ''
    machine_hebergement = (data.get('machine_hebergement') or '').strip() if type_deploiement == 'Self-hosted' else None
    type_licence = data.get('type_licence') or 'Perpétuelle'
    date_expiration = (data.get('date_expiration') or '').strip() if type_licence == 'Limitée' else None
    url_rss = (data.get('url_rss') or '').strip() or None
    responsable = (data.get('responsable') or '').strip().upper()

    # Gestion des entités (peut être fourni sous forme de liste ou de chaine)
    entites = data.get('entites', 'Groupe')
    if isinstance(entites, list):
        entites = ', '.join(entites)
    if not entites or not entites.strip():
        entites = 'Groupe'

    if not nom_produit or not version_actuelle or not type_deploiement or not responsable:
        return jsonify({'error': 'Les champs Nom du produit, version actuelle, type de déploiement et responsable sont requis.'}), 400

    if type_deploiement == 'Self-hosted' and not machine_hebergement:
        return jsonify({'error': 'Le champ Machine / Serveur d\'hébergement est obligatoire pour un déploiement Self-hosted.'}), 400

    if type_licence == 'Limitée' and not date_expiration:
        return jsonify({'error': 'La date d\'expiration est obligatoire pour une licence Limitée.'}), 400

    conn = get_db_connection()
    # Vérifier que le responsable existe
    resp_check = conn.execute("SELECT 1 FROM team WHERE trigramme = ?;", (responsable,)).fetchone()
    if not resp_check:
        conn.close()
        return jsonify({'error': f'Le responsable avec le trigramme {responsable} n\'existe pas.'}), 400

    try:
        cursor = conn.execute("""
            INSERT INTO assets (nom_produit, fournisseur, version_actuelle, type_deploiement, machine_hebergement, type_licence, date_expiration, url_rss, responsable, entites)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (nom_produit, fournisseur, version_actuelle, type_deploiement, machine_hebergement, type_licence, date_expiration, url_rss, responsable, entites))
        conn.commit()
        asset_id = cursor.lastrowid
    except Exception as e:
        conn.close()
        return jsonify({'error': f'Erreur de base de données : {str(e)}'}), 500

    conn.close()
    return jsonify({'id': asset_id, 'success': True}), 201

@app.route('/api/assets/<int:asset_id>', methods=['PUT'])
def update_asset(asset_id):
    data = request.json
    nom_produit = (data.get('nom_produit') or '').strip()
    fournisseur = (data.get('fournisseur') or '').strip() or None
    version_actuelle = (data.get('version_actuelle') or '').strip()
    type_deploiement = data.get('type_deploiement') or ''
    machine_hebergement = (data.get('machine_hebergement') or '').strip() if type_deploiement == 'Self-hosted' else None
    type_licence = data.get('type_licence') or 'Perpétuelle'
    date_expiration = (data.get('date_expiration') or '').strip() if type_licence == 'Limitée' else None
    url_rss = (data.get('url_rss') or '').strip() or None
    responsable = (data.get('responsable') or '').strip().upper()

    # Gestion des entités (peut être fourni sous forme de liste ou de chaine)
    entites = data.get('entites', 'Groupe')
    if isinstance(entites, list):
        entites = ', '.join(entites)
    if not entites or not entites.strip():
        entites = 'Groupe'

    if not nom_produit or not version_actuelle or not type_deploiement or not responsable:
        return jsonify({'error': 'Les champs Nom du produit, version actuelle, type de déploiement et responsable sont requis.'}), 400

    if type_deploiement == 'Self-hosted' and not machine_hebergement:
        return jsonify({'error': 'Le champ Machine / Serveur d\'hébergement est obligatoire pour un déploiement Self-hosted.'}), 400

    if type_licence == 'Limitée' and not date_expiration:
        return jsonify({'error': 'La date d\'expiration est obligatoire pour une licence Limitée.'}), 400

    conn = get_db_connection()
    # Vérifier que le responsable existe
    resp_check = conn.execute("SELECT 1 FROM team WHERE trigramme = ?;", (responsable,)).fetchone()
    if not resp_check:
        conn.close()
        return jsonify({'error': f'Le responsable avec le trigramme {responsable} n\'existe pas.'}), 400

    try:
        conn.execute("""
            UPDATE assets 
            SET nom_produit = ?, fournisseur = ?, version_actuelle = ?, type_deploiement = ?, 
                machine_hebergement = ?, type_licence = ?, date_expiration = ?, url_rss = ?, responsable = ?, entites = ?
            WHERE id = ?;
        """, (nom_produit, fournisseur, version_actuelle, type_deploiement, machine_hebergement, type_licence, date_expiration, url_rss, responsable, entites, asset_id))
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({'error': f'Erreur de base de données : {str(e)}'}), 500

    conn.close()
    return jsonify({'success': True})

@app.route('/api/assets/<int:asset_id>', methods=['DELETE'])
def delete_asset(asset_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM assets WHERE id = ?;", (asset_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# 3. Actions prioritaires (Alertes RSS d'actifs)
@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    conn = get_db_connection()
    alerts_raw = conn.execute("""
        SELECT al.*, asst.nom_produit as nom_produit, asst.responsable as responsable, asst.version_actuelle as version_actuelle
        FROM alerts al
        JOIN assets asst ON al.asset_id = asst.id
        WHERE al.resolved = 0
        ORDER BY al.pub_date DESC, al.id DESC;
    """).fetchall()
    conn.close()
    
    filtered_alerts = []
    for a in alerts_raw:
        alert_dict = dict(a)
        status, priority, status_text, affected_versions = analyze_alert(alert_dict)
        if status != 'hide':
            alert_dict['priority'] = priority
            alert_dict['status_text'] = status_text
            alert_dict['affected_versions'] = affected_versions
            filtered_alerts.append(alert_dict)
            
    return jsonify(filtered_alerts)

@app.route('/api/alerts/resolve/<int:alert_id>', methods=['POST'])
def resolve_alert(alert_id):
    conn = get_db_connection()
    conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?;", (alert_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/alerts/refresh', methods=['POST'])
def refresh_alerts():
    conn = get_db_connection()
    assets = conn.execute("SELECT id, nom_produit, url_rss FROM assets WHERE url_rss IS NOT NULL AND url_rss != '';").fetchall()
    
    unreachable_urls = []
    new_alerts_count = 0
    
    for asset in assets:
        asset_id = asset['id']
        url = asset['url_rss']
        
        feed_items = fetch_rss_feed(url)
        if feed_items is None:
            unreachable_urls.append(url)
            continue
            
        for item in feed_items:
            title = item['title']
            link = item['link']
            pub_date = item['pub_date']
            
            # Vérifier si l'alerte existe déjà
            existing = conn.execute("""
                SELECT 1 FROM alerts 
                WHERE asset_id = ? AND (title = ? OR (link = ? AND link != ''));
            """, (asset_id, title, link)).fetchone()
            
            if not existing:
                description = item.get('description', '')
                conn.execute("""
                    INSERT INTO alerts (asset_id, title, description, link, pub_date, resolved)
                    VALUES (?, ?, ?, ?, ?, 0);
                """, (asset_id, title, description, link, pub_date))
                new_alerts_count += 1
                
    conn.commit()
    
    # Récupérer les alertes restantes non résolues
    alerts_raw = conn.execute("""
        SELECT al.*, asst.nom_produit as nom_produit, asst.responsable as responsable, asst.version_actuelle as version_actuelle
        FROM alerts al
        JOIN assets asst ON al.asset_id = asst.id
        WHERE al.resolved = 0
        ORDER BY al.pub_date DESC, al.id DESC;
    """).fetchall()
    
    conn.close()
    
    filtered_alerts = []
    for a in alerts_raw:
        alert_dict = dict(a)
        status, priority, status_text, affected_versions = analyze_alert(alert_dict)
        if status != 'hide':
            alert_dict['priority'] = priority
            alert_dict['status_text'] = status_text
            alert_dict['affected_versions'] = affected_versions
            filtered_alerts.append(alert_dict)
            
    return jsonify({
        'alerts': filtered_alerts,
        'new_alerts_count': new_alerts_count,
        'unreachable_urls': unreachable_urls
    })

# 4. Bulletins globaux CERT-FR
@app.route('/api/cert-rss', methods=['GET'])
def get_cert_rss():
    items = fetch_rss_feed(CERT_FR_FEED_URL)
    if items is None:
        return jsonify({
            'error': 'Le flux CERT-FR est temporairement injoignable.',
            'items': []
        }), 502
    # Retourne les 5 derniers bulletins
    return jsonify({'items': items[:5]})

# 5. Statistiques du Tableau de bord (KPIs)
@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db_connection()
    
    # Actifs & Services (Total)
    total_assets = conn.execute("SELECT COUNT(*) FROM assets;").fetchone()[0]
    
    # Alertes en attente (uniquement celles visibles après filtrage)
    alerts_raw = conn.execute("""
        SELECT al.*, asst.version_actuelle as version_actuelle
        FROM alerts al
        JOIN assets asst ON al.asset_id = asst.id
        WHERE al.resolved = 0;
    """).fetchall()
    
    pending_alerts = 0
    for a in alerts_raw:
        status, _, _, _ = analyze_alert(dict(a))
        if status != 'hide':
            pending_alerts += 1
    
    # Licences expirant dans moins de 30 jours
    assets_with_expiry = conn.execute("""
        SELECT date_expiration 
        FROM assets 
        WHERE type_licence = 'Limitée' AND date_expiration IS NOT NULL AND date_expiration != '';
    """).fetchall()
    
    expiring_soon = 0
    today = date.today() # Par rapport à la date actuelle (2026-07-09)
    
    for asset in assets_with_expiry:
        try:
            exp_date = datetime.strptime(asset['date_expiration'], "%Y-%m-%d").date()
            delta = (exp_date - today).days
            if 0 <= delta < 30:
                expiring_soon += 1
        except Exception:
            pass
            
    conn.close()
    
    return jsonify({
        'total_assets': total_assets,
        'pending_alerts': pending_alerts,
        'expiring_licences': expiring_soon
    })

# Redirection vers l'application frontend en production
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    # Initialisation de la base si elle n'existe pas
    if not os.path.exists(DB_PATH):
        from init_db import init_db as init_db_func
        init_db_func()
    app.run(host='0.0.0.0', port=5000, debug=True)
