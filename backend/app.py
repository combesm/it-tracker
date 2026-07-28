from flask import Flask, jsonify, request, send_from_directory, make_response
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
import re
import json
import base64
import secrets
from werkzeug.security import check_password_hash
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

def compare_versions_normalized(ver_a, ver_b):
    """
    Compare deux objets Version de manière robuste.
    Si l'un a un segment majeur '0' ou '1' (que l'autre n'a pas, car commençant par >= 10),
    on dé-préfixe ce segment pour permettre la comparaison de la branche mineure (ex: 0.63 vs 57.1).
    """
    parts_a = list(ver_a.release)
    parts_b = list(ver_b.release)
    
    norm_a = parts_a
    norm_b = parts_b
    
    if len(parts_a) > 1 and parts_a[0] in (0, 1) and len(parts_b) > 0 and parts_b[0] >= 10:
        norm_a = parts_a[1:]
    elif len(parts_b) > 1 and parts_b[0] in (0, 1) and len(parts_a) > 0 and parts_a[0] >= 10:
        norm_b = parts_b[1:]
        
    str_a = ".".join(map(str, norm_a))
    str_b = ".".join(map(str, norm_b))
    
    if ver_a.pre:
        str_a += f"-{ver_a.pre[0]}{ver_a.pre[1]}"
    if ver_b.pre:
        str_b += f"-{ver_b.pre[0]}{ver_b.pre[1]}"
        
    try:
        val_a = Version(str_a)
        val_b = Version(str_b)
        if val_a < val_b:
            return -1
        elif val_a > val_b:
            return 1
        return 0
    except Exception:
        if ver_a < ver_b:
            return -1
        elif ver_a > ver_b:
            return 1
        return 0

def analyze_alert(alert):
    title = alert.get('title') or ''
    description = alert.get('description') or ''
    version_actuelle = alert.get('version_actuelle') or ''
    
    # Détection de type CVE (soit via CVSS dans le titre, soit via présence d'un motif CVE-XXXX-XXXXX)
    cvss_match = re.search(r'\[CVE / CVSS:\s*(\d+(?:\.\d+)?)\]', title)
    cve_id_match = re.search(r'\b(CVE-\d{4}-\d{4,})\b', title)
    
    if cvss_match or cve_id_match:
        cvss_score = None
        priority = 'medium'
        status_text = 'Vulnérabilité (CVSS non disponible)'
        
        if cvss_match:
            cvss_score = float(cvss_match.group(1))
            if cvss_score >= 9.0:
                priority = 'critical'
                status_text = f'Vulnérabilité Critique (CVSS: {cvss_score})'
            elif cvss_score >= 7.0:
                priority = 'high'
                status_text = f'Vulnérabilité Élevée (CVSS: {cvss_score})'
            elif cvss_score >= 4.0:
                priority = 'medium'
                status_text = f'Vulnérabilité Moyenne (CVSS: {cvss_score})'
            else:
                priority = 'low'
                status_text = f'Vulnérabilité Faible (CVSS: {cvss_score})'
                
        # Vérification des versions impactées
        impacted_ver_text = "Détectée"
        if "Versions impactées détectées :" in description:
            impacted_matches = re.findall(r'<li>[^(]+\(([^)]+)\)</li>', description)
            if impacted_matches:
                impacted_ver_text = ", ".join(impacted_matches)
                is_vulnerable = False
                asset_ver = parse_version_safe(version_actuelle)
                
                for spec in impacted_matches:
                    spec = spec.strip()
                    # Déterminer s'il s'agit d'une contrainte d'inégalités combinées (AND)
                    if any(op in spec for op in ('<=', '<', '>=', '>', '&lt;=', '&lt;', '&gt;=', '&gt;')):
                        parts = [p.strip() for p in spec.split(',') if p.strip()]
                        spec_ok = True
                        for part in parts:
                            part_matched = False
                            op_match = re.match(r'^(&(?:lt|gt);=?|<=|>=|<|>)?\s*(.*)$', part)
                            if op_match:
                                op = op_match.group(1)
                                v_str = op_match.group(2).strip()
                                if not op:
                                    if part == version_actuelle:
                                        part_matched = True
                                    else:
                                        v = parse_version_safe(part)
                                        if asset_ver and v and compare_versions_normalized(asset_ver, v) == 0:
                                            part_matched = True
                                else:
                                    v = parse_version_safe(v_str)
                                    if asset_ver and v:
                                        comp = compare_versions_normalized(asset_ver, v)
                                        if op in ('<=', '&lt;='):
                                            part_matched = (comp <= 0)
                                        elif op in ('<', '&lt;'):
                                            part_matched = (comp < 0)
                                        elif op in ('>=', '&gt;='):
                                            part_matched = (comp >= 0)
                                        elif op in ('>', '&gt;'):
                                            part_matched = (comp > 0)
                            if not part_matched:
                                spec_ok = False
                                break
                        if spec_ok:
                            is_vulnerable = True
                            break
                    else:
                        # Relation OR pour les versions standards et plages avec tirets
                        parts = [p.strip() for p in spec.split(',') if p.strip()]
                        for part in parts:
                            part_matched = False
                            match_hyphen = re.match(r'^([^-]+)\s*-\s*([^-]+)$', part)
                            if match_hyphen:
                                v_min_str = match_hyphen.group(1).strip()
                                v_max_str = match_hyphen.group(2).strip()
                                v_min = parse_version_safe(v_min_str)
                                v_max = parse_version_safe(v_max_str)
                                if asset_ver and v_min and v_max:
                                    comp_min = compare_versions_normalized(asset_ver, v_min)
                                    comp_max = compare_versions_normalized(asset_ver, v_max)
                                    if comp_min >= 0 and comp_max <= 0:
                                        part_matched = True
                            else:
                                if part == version_actuelle:
                                    part_matched = True
                                else:
                                    v = parse_version_safe(part)
                                    if asset_ver and v and compare_versions_normalized(asset_ver, v) == 0:
                                        part_matched = True
                            if part_matched:
                                is_vulnerable = True
                                break
                        if is_vulnerable:
                            break
                
                if not is_vulnerable:
                    return 'hide', None, None, None
                    
        return 'show', priority, status_text, impacted_ver_text

    # 0. Détection d'alerte de mise à jour Joomla (ex: "Mise à jour disponible : Version 2.9.71 disponible (Actuellement en 2.9.70)")
    joomla_match = re.search(r'Mise à jour disponible\s*:\s*Version\s+([^\s]+)\s+disponible', title)
    if joomla_match:
        xml_ver_str = joomla_match.group(1).strip()
        rss_ver = parse_version_safe(xml_ver_str)
        asset_ver = parse_version_safe(version_actuelle)
        
        if rss_ver is None:
            return 'show', 'manual_check', 'Vérification manuelle de la version requise', 'Non déterminée'
        if asset_ver is None:
            return 'show', 'manual_check', 'Vérification manuelle de la version requise', xml_ver_str
        if rss_ver <= asset_ver:
            return 'hide', None, None, None
        else:
            return 'show', 'update_available', 'Mise à jour disponible', xml_ver_str
    
    # Masquer les alertes de pré-release (nightly, beta, alpha, rc, dev...)
    # si l'utilisateur utilise une version stable (uniquement basé sur le titre de l'alerte pour éviter
    # les faux positifs avec le texte de description comme "source", "device", etc.)
    prerelease_pattern = r'\b(nightly|beta|alpha|rc[.-]?\d*|dev|test|preview)\b'
    has_prerelease_alert = bool(re.search(prerelease_pattern, title.lower()))
    has_prerelease_asset = bool(re.search(prerelease_pattern, version_actuelle.lower()))
    
    if has_prerelease_alert and not has_prerelease_asset:
        return 'hide', None, None, None

    # 1. Flux de Releases (ex: GitHub releases)
    # Le titre contient uniquement la version (ex: "v0.62.4" ou "0.62.4")
    # ou une version a été extraite de l'entrée du flux (comme dans le cas de GophishFR)
    extracted_ver_str = alert.get('extracted_version')
    version_pattern = r'^v?\d+(?:\.\d+)+(?:-[a-zA-Z0-9.]+)?$'
    clean_title = title.strip()
    
    is_release_feed = False
    ver_to_check = None
    
    if extracted_ver_str:
        is_release_feed = True
        ver_to_check = extracted_ver_str
    elif re.match(version_pattern, clean_title, re.IGNORECASE):
        is_release_feed = True
        ver_to_check = clean_title
        
    if is_release_feed and ver_to_check:
        rss_ver = parse_version_safe(ver_to_check)
        asset_ver = parse_version_safe(version_actuelle)
        
        if rss_ver is None:
            return 'show', 'manual_check', 'Vérification manuelle de la version requise', 'Non déterminée'
            
        if asset_ver is None:
            return 'show', 'manual_check', 'Vérification manuelle de la version requise', ver_to_check
            
        if rss_ver <= asset_ver:
            return 'hide', None, None, None
        else:
            return 'show', 'update_available', 'Mise à jour disponible', ver_to_check
            
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

DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'database.db'))
# S'assurer que le dossier parent de la base existe
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    try:
        os.makedirs(db_dir, exist_ok=True)
    except Exception as e:
        print(f"Impossible de créer le dossier de base de données {db_dir} : {e}")

CERT_FR_FEED_URL = "https://www.cert.ssi.gouv.fr/feed/"

def validate_and_clean_url(url):
    if not url:
        return None
    url = url.strip()
    if url.lower().startswith('opencve://'):
        parts = [p for p in url.replace('opencve://', '').split('/') if p]
        if len(parts) >= 2 and parts[0] in ('vendor', 'product'):
            return url
        return None
        
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return None
    if not parsed.netloc:
        return None
        
    hostname = parsed.hostname
    if not hostname:
        return None
        
    hostname_lower = hostname.lower().strip()
    if hostname_lower in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
        return None
    if hostname_lower.startswith('169.254.'):
        return None
        
    return url

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def send_teams_notification(webhook_url, alert_title, alert_desc, alert_link, asset_name, asset_version, cve_id, cvss_score, priority, pub_date, responsable=None):
    if not webhook_url:
        return False, "URL Webhook vide"
    
    # Calcul de la couleur, du style et de l'affichage du CVSS
    cvss_val = None
    if cvss_score is not None:
        try:
            cvss_val = float(cvss_score)
        except ValueError:
            pass

    if cvss_val is not None:
        if cvss_val >= 9.0:
            card_style = "attention"  # Rouge
            text_color = "attention"
            cvss_display = f"🔴 {cvss_val} (CRITIQUE)"
        elif cvss_val >= 7.0:
            card_style = "warning"    # Orange / Jaune
            text_color = "warning"
            cvss_display = f"🟠 {cvss_val} (ÉLEVÉ)"
        elif cvss_val >= 4.0:
            card_style = "accent"     # Bleu
            text_color = "accent"
            cvss_display = f"🟡 {cvss_val} (MOYEN)"
        else:
            card_style = "good"       # Vert
            text_color = "good"
            cvss_display = f"🟢 {cvss_val} (BAS)"
    else:
        p_lower = priority.lower() if priority else ""
        if p_lower == 'critical':
            card_style = "attention"
            text_color = "attention"
            cvss_display = "🔴 N/A"
        elif p_lower == 'high':
            card_style = "warning"
            text_color = "warning"
            cvss_display = "🟠 N/A"
        elif p_lower in ('medium', 'update_available'):
            card_style = "accent"
            text_color = "accent"
            cvss_display = "🟡 N/A" if p_lower == 'medium' else "🔵 N/A"
        elif p_lower == 'low':
            card_style = "good"
            text_color = "good"
            cvss_display = "🟢 N/A"
        else:
            card_style = "default"
            text_color = "default"
            cvss_display = "⚪ N/A"

    # Construction de l'Adaptive Card Teams (v1.4)
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "style": card_style,
                            "bleed": True,
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "🚨 Faille de sécurité détectée" if cve_id else "🔔 Mise à jour ou Alerte",
                                    "weight": "Bolder",
                                    "size": "Large",
                                    "color": text_color
                                }
                            ]
                        },
                        {
                            "type": "Container",
                            "spacing": "Medium",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"Produit : **{asset_name}**",
                                    "size": "Medium",
                                    "weight": "Bolder",
                                    "wrap": True
                                },
                                {
                                    "type": "TextBlock",
                                    "text": f"Version installée : {asset_version}",
                                    "isSubtle": True,
                                    "spacing": "None",
                                    "wrap": True
                                },
                                {
                                    "type": "FactSet",
                                    "facts": [
                                        { "title": "Alerte / Titre", "value": alert_title or "Non spécifié" },
                                        { "title": "Score CVSS", "value": cvss_display },
                                        { "title": "Criticité", "value": priority.upper() if priority else "N/A" },
                                        { "title": "Responsable", "value": responsable or "Non spécifié" },
                                        { "title": "Date pub.", "value": pub_date or "Non spécifiée" }
                                    ],
                                    "spacing": "Medium"
                                }
                            ]
                        }
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "Voir la source de l'alerte",
                            "url": alert_link
                        }
                    ] if alert_link else []
                }
            }
        ]
    }
        
    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_code = response.getcode()
            if res_code in (200, 201, 202):
                return True, ""
            else:
                return False, f"Code HTTP inattendu : {res_code}"
    except Exception as e:
        return False, str(e)

# Helper: Récupération des vulnérabilités depuis l'API REST d'OpenCVE
def fetch_opencve_feed(url):
    opencve_url = os.getenv('OPENCVE_URL', 'http://host.docker.internal:8000').rstrip('/')
    opencve_user = os.getenv('OPENCVE_USER', 'api_admin')
    opencve_password = os.getenv('OPENCVE_PASSWORD')
    if not opencve_password:
        print("[AVERTISSEMENT] OPENCVE_PASSWORD non défini dans l'environnement. La récupération des flux OpenCVE est désactivée.")
        return None
    opencve_token = os.getenv('OPENCVE_TOKEN')
    
    # Format attendu : opencve://vendor/<vendor> ou opencve://product/<vendor>/<product>
    path = url.replace('opencve://', '')
    parts = [p for p in path.split('/') if p]
    
    if not parts:
        return []
        
    query_type = parts[0] # 'vendor' ou 'product'
    vendor = parts[1] if len(parts) >= 2 else None
    product = parts[2] if len(parts) >= 3 else None
    
    api_url = f"{opencve_url}/api/cve"
    if query_type == 'vendor' and vendor:
        api_url += f"?vendor={urllib.parse.quote(vendor)}"
    elif query_type == 'product' and vendor and product:
        # Normalisation automatique pour Joomla (qui s'écrit joomlack.fr ou joomla\! dans le dictionnaire CPE)
        if vendor.lower() == 'joomla' and product.lower() in ('joomla', 'joomla!', 'joomla\\!', 'joomla\\\\!'):
            product = 'joomla\\!'
        api_url += f"?vendor={urllib.parse.quote(vendor)}&product={urllib.parse.quote(product)}"
        
    # Headers
    host_val = os.getenv('OPENCVE_HOST_HEADER')
    if not host_val:
        parsed = urllib.parse.urlparse(opencve_url)
        host_val = parsed.hostname
        
    auth_b64 = None
    if not opencve_token:
        auth_str = f"{opencve_user}:{opencve_password}"
        auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        
    def perform_request(target_url):
        req = urllib.request.Request(target_url)
        if host_val:
            req.add_header('Host', host_val)
        if opencve_token:
            req.add_header('Authorization', f'Bearer {opencve_token}')
        else:
            req.add_header('Authorization', f'Basic {auth_b64}')
        req.add_header('User-Agent', 'herakles-it-tracker/1.0')
        req.add_header('Accept', 'application/json')
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read()

    # Toujours combiner l'appel direct et la recherche de fallback
    candidates = {}
    
    # 1. Appel direct
    try:
        res_data = perform_request(api_url)
        cve_list = json.loads(res_data)
        search_list = []
        if isinstance(cve_list, dict) and 'results' in cve_list:
            search_list = cve_list['results']
        elif isinstance(cve_list, list):
            search_list = cve_list
        for cve_sum in search_list:
            if 'id' in cve_sum:
                candidates[cve_sum['id']] = cve_sum
    except Exception as e:
        print(f"Erreur d'appel direct OpenCVE ({api_url}) : {e}")

    # 2. Recherche complémentaire par mot-clé
    search_terms = []
    if vendor and len(vendor) >= 3:
        search_terms.append(vendor)
        clean_v = re.sub(r'\.(com|org|net|fr|io|edu|gov|co|info|biz|us|de|uk|eu)\b', '', vendor.lower())
        if clean_v != vendor.lower() and len(clean_v) >= 3:
            search_terms.append(clean_v)
    if product:
        p_parts = [p for p in re.split(r'[-_ ]', product) if p]
        if p_parts and len(p_parts[0]) >= 3:
            search_terms.append(p_parts[0])
            
    for term in search_terms:
        try:
            search_url = f"{opencve_url}/api/cve?search={urllib.parse.quote(term)}"
            search_data_bytes = perform_request(search_url)
            search_data = json.loads(search_data_bytes)
            search_list = []
            if isinstance(search_data, dict) and 'results' in search_data:
                search_list = search_data['results']
            elif isinstance(search_data, list):
                search_list = search_data
                
            for cve_sum in search_list:
                if 'id' in cve_sum:
                    candidates[cve_sum['id']] = cve_sum
        except Exception as e_search:
            print(f"Erreur de recherche complémentaire pour {term}: {e_search}")

    # Helper de normalisation de chaîne pour tolérer les variations mineures (suffixes client, project, cms, .com, etc.)
    def normalize_name(name):
        if not name:
            return ""
        n = name.lower()
        # Supprimer les extensions de domaine (.fr, .org, .com etc)
        n = re.sub(r'\.(com|org|net|fr|io|edu|gov|co|info|biz|us|de|uk|eu)\b', '', n)
        # Supprimer les suffixes / mots clés génériques
        n = re.sub(r'\b(client|server|project|cms|extension|plugin|theme|module|software|app|application|framework)\b', '', n)
        # Remplacer les caractères non-alphanumériques par du vide
        n = re.sub(r'[^a-z0-9]', '', n)
        return n

    # Récupérer les alertes existantes pour ce flux afin d'éviter les doubles fetches
    conn = get_db_connection()
    existing_titles = [row['title'] for row in conn.execute("SELECT title FROM alerts WHERE trigger_url = ?;", (url,)).fetchall()]
    conn.close()

    # Filtrer les candidats
    norm_vendor = normalize_name(vendor)
    norm_product = normalize_name(product)
    
    filtered_results = []
    
    # Limiter le nombre de candidats évalués (jusqu'à 50 candidats grâce au multi-threading)
    candidates_items = list(candidates.items())[:50]
    
    def process_candidate(cve_item):
        cve_id, cve_sum = cve_item
        if any(cve_id in t for t in existing_titles):
            return None
            
        try:
            detail_url = f"{opencve_url}/api/cve/{cve_id}"
            detail_data_bytes = perform_request(detail_url)
            cve_detail = json.loads(detail_data_bytes)
        except Exception as e_detail:
            print(f"Erreur de récupération détails pour {cve_id} (fallback): {e_detail}")
            return None
            
        raw_nvd = cve_detail.get('raw_nvd_data') or {}
        affected_list = raw_nvd.get('affected') or []
        matched = False
        
        # Distinction Client/Serveur pour le résumé ou les métadonnées
        is_server_query = "server" in (vendor or "").lower() or "server" in (product or "").lower()
        
        if not affected_list:
            # Si pas de liste d'affected, on cherche dans le résumé
            summary = cve_sum.get('summary') or ''
            is_server_nvd = "server" in summary.lower()
            if is_server_query == is_server_nvd:
                if product:
                    if product.lower() in summary.lower() or (vendor and vendor.lower() in summary.lower()):
                        matched = True
                else:
                    if vendor and vendor.lower() in summary.lower():
                        matched = True
        else:
            for aff in affected_list:
                aff_data = aff.get('affectedData') or []
                for data_item in aff_data:
                    v_val = data_item.get('vendor')
                    p_val = data_item.get('product')
                    if not v_val or not p_val:
                        continue
                        
                    is_server_nvd = "server" in v_val.lower() or "server" in p_val.lower()
                    if is_server_query != is_server_nvd:
                        continue
                        
                    norm_v_val = normalize_name(v_val)
                    norm_p_val = normalize_name(p_val)
                    
                    if product:
                        if (norm_vendor in norm_v_val or norm_v_val in norm_vendor) and (norm_product in norm_p_val or norm_p_val in norm_product):
                            matched = True
                            break
                    else:
                        if norm_vendor in norm_v_val or norm_v_val in norm_vendor:
                            matched = True
                            break
                if matched:
                    break
                    
        if matched:
            cve_sum['_cached_detail'] = cve_detail
            return cve_sum
        return None

    if candidates_items:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_candidate, item) for item in candidates_items]
            for f in as_completed(futures):
                try:
                    res = f.result()
                    if res:
                        filtered_results.append(res)
                except Exception as e_cand:
                    print(f"Erreur évaluation candidat OpenCVE: {e_cand}")

    # Récupérer les détails et construire la liste d'alertes finale
    items = []
    for cve in filtered_results:
        cve_id = cve.get('id') or 'CVE-Unknown'
        summary = cve.get('summary') or 'Aucun résumé fourni.'
        pub_date = cve.get('published_at') or cve.get('updated_at') or ''
        
        cvss_score = None
        cvss_severity = None
        
        # Récupérer depuis le cache ou fetcher au besoin
        cve_detail = cve.get('_cached_detail')
        if not cve_detail:
            detail_url = f"{opencve_url}/api/cve/{cve_id}"
            try:
                d_resp_data = perform_request(detail_url)
                cve_detail = json.loads(d_resp_data)
            except Exception as e_detail:
                print(f"Erreur de récupération tardive des détails pour {cve_id}: {e_detail}")
                cve_detail = {}
                
        cvss_dict = cve_detail.get('cvss') or {}
        cvss_score = cvss_dict.get('v3')
        if cvss_score is None:
            cvss_score = cvss_dict.get('v2')
            
        # Fallback pour extraire le score CVSS (notamment V4.0 ou V3/V2 s'ils sont uniquement dans raw_nvd_data)
        if cvss_score is None:
            raw_nvd = cve_detail.get('raw_nvd_data') or {}
            metrics = raw_nvd.get('metrics') or {}
            
            # 1. Tenter CVSS v4.0
            if 'cvssMetricV40' in metrics and isinstance(metrics['cvssMetricV40'], list) and len(metrics['cvssMetricV40']) > 0:
                cvss_score = metrics['cvssMetricV40'][0].get('cvssData', {}).get('baseScore')
            
            # 2. Tenter CVSS v3.1
            if cvss_score is None and 'cvssMetricV31' in metrics and isinstance(metrics['cvssMetricV31'], list) and len(metrics['cvssMetricV31']) > 0:
                cvss_score = metrics['cvssMetricV31'][0].get('cvssData', {}).get('baseScore')
                
            # 3. Tenter CVSS v3.0
            if cvss_score is None and 'cvssMetricV30' in metrics and isinstance(metrics['cvssMetricV30'], list) and len(metrics['cvssMetricV30']) > 0:
                cvss_score = metrics['cvssMetricV30'][0].get('cvssData', {}).get('baseScore')
                
            # 4. Tenter CVSS v2
            if cvss_score is None and 'cvssMetricV2' in metrics and isinstance(metrics['cvssMetricV2'], list) and len(metrics['cvssMetricV2']) > 0:
                cvss_score = metrics['cvssMetricV2'][0].get('cvssData', {}).get('baseScore')
        
        if cvss_score is not None:
            try:
                cvss_score = float(cvss_score)
                if cvss_score >= 9.0:
                    cvss_severity = "CRITICAL"
                elif cvss_score >= 7.0:
                    cvss_severity = "HIGH"
                elif cvss_score >= 4.0:
                    cvss_severity = "MEDIUM"
                else:
                    cvss_severity = "LOW"
            except ValueError:
                cvss_score = None
            
        affected_vers = []
        raw_nvd = cve_detail.get('raw_nvd_data') or {}
        affected_list = raw_nvd.get('affected') or []
        for aff in affected_list:
            aff_data = aff.get('affectedData') or []
            for data_item in aff_data:
                v_name = data_item.get('vendor')
                p_name = data_item.get('product')
                if not v_name or not p_name or v_name == 'n/a' or p_name == 'n/a':
                    continue
                    
                versions_list = []
                # Gérer versions et plages d'impact explicites (gte, gt, lte, lt)
                for v_item in data_item.get('versions') or []:
                    v_val = v_item.get('version')
                    gte = v_item.get('greaterThanOrEqual') or v_item.get('greaterThan')
                    lte = v_item.get('lessThanOrEqual') or v_item.get('lessThan')
                    
                    if v_val and any(op in str(v_val) for op in ('>', '<', '=')):
                        versions_list.append(v_val)
                        continue
                        
                    bounds = []
                    # 1. Borne inférieure
                    if gte:
                        op_gt = '>=' if 'greaterThanOrEqual' in v_item else '>'
                        bounds.append(f"{op_gt} {gte}")
                    elif v_val and v_val != 'n/a' and v_val != '0':
                        # Si une borne supérieure est présente, v_val représente le début de la plage (donc >= v_val)
                        if lte:
                            bounds.append(f">= {v_val}")
                        
                    # 2. Borne supérieure
                    if lte:
                        op_lt = '<=' if 'lessThanOrEqual' in v_item else '<'
                        bounds.append(f"{op_lt} {lte}")
                        
                    if bounds:
                        versions_list.append(", ".join(bounds))
                    elif v_val and v_val != 'n/a':
                        versions_list.append(v_val)
                        
                if not versions_list:
                    for cpe_str in data_item.get('cpes') or []:
                        cpe_parts = cpe_str.split(':')
                        if len(cpe_parts) >= 6:
                            cpe_ver = cpe_parts[5]
                            if cpe_ver and cpe_ver not in ('*', '-'):
                                versions_list.append(cpe_ver)
                                
                if versions_list:
                    unique_vers = list(dict.fromkeys(versions_list))
                    affected_vers.append(f"{v_name} {p_name} ({', '.join(unique_vers)})")
                    
        desc_html = ""
        if cvss_score is not None:
            severity_label = f" ({cvss_severity})" if cvss_severity else ""
            desc_html += f"<p><strong>Score CVSS :</strong> <span style='font-weight: bold; color: #dc2626;'>{cvss_score}</span>{severity_label}</p>"
            
        desc_html += f"<p>{summary}</p>"
        if affected_vers:
            desc_html += "<p><strong>Versions impactées détectées :</strong></p><ul>"
            for av in affected_vers:
                desc_html += f"<li>{av}</li>"
            desc_html += "</ul>"
            
        if cvss_score is not None:
            title = f"[CVE / CVSS: {cvss_score}] {cve_id} - {summary[:80]}..."
        else:
            title = f"{cve_id} - {summary[:80]}..."
            
        items.append({
            'title': title,
            'link': f"https://www.cve.org/CVERecord?id={cve_id}",
            'pub_date': pub_date,
            'description': desc_html
        })
        
    return items

# Helper : extraire proprement la version depuis le titre, le lien ou l'ID d'une entrée de flux
def extract_version_from_entry(title, link, entry_id=None):
    version_regex = r'\b(?:v)?(\d+\.\d+(?:\.\d+)*(?:-[a-zA-Z0-9.]+)?)\b'
    version_pattern = r'^v?\d+(?:\.\d+)+(?:-[a-zA-Z0-9.]+)?$'
    
    if title:
        clean_title = title.strip()
        if re.match(version_pattern, clean_title, re.IGNORECASE):
            return clean_title
            
    if link:
        match_link = re.search(r'/tags?/(v?\d+(?:\.\d+)+(?:-[a-zA-Z0-9.]+)?)\b', link, re.IGNORECASE)
        if match_link:
            return match_link.group(1)
            
    if entry_id:
        match_id = re.search(r'/(v?\d+(?:\.\d+)+(?:-[a-zA-Z0-9.]+)?)$', entry_id, re.IGNORECASE)
        if match_id:
            return match_id.group(1)
            
    if title:
        match_title = re.search(version_regex, title, re.IGNORECASE)
        if match_title:
            return match_title.group(0)
            
    return None

# Helper: Parseur RSS générique et robuste
def fetch_rss_feed(url, xml_data=None):
    if url.lower().startswith('opencve://'):
        return fetch_opencve_feed(url)
    try:
        if xml_data is None:
            clean_url = validate_and_clean_url(url)
            if not clean_url:
                print(f"URL de flux RSS bloquée pour des raisons de sécurité : {url}")
                return None
                
            req = urllib.request.Request(
                clean_url, 
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
            
            # Extraction de l'ID/guid de l'entrée
            id_elem = find_child(item_elem, 'id')
            if id_elem is None:
                id_elem = find_child(item_elem, 'guid')
            id_text = id_elem.text if id_elem is not None else ""
            
            # Ignorer les tags génériques redondants (comme latest-oss, latest-ee, latest, stable)
            # qui polluent les flux de releases GitHub
            clean_title = title_text.strip().lower()
            if clean_title in ('latest-oss', 'latest-ee', 'latest', 'stable', 'release-candidate', 'current-stable'):
                continue
            if link_text:
                lower_link = link_text.lower()
                if any(f"/tag/{g}" in lower_link or f"/tags/{g}" in lower_link or lower_link.endswith(f"/{g}") for g in ('latest-oss', 'latest-ee', 'latest', 'stable')):
                    continue
                    
            extracted_ver = extract_version_from_entry(title_text, link_text, id_text)
            
            items.append({
                'title': title_text,
                'link': link_text,
                'pub_date': pub_date_text,
                'description': desc_text,
                'extracted_version': extracted_ver
            })
        return items
    except Exception as e:
        print(f"Erreur de récupération du flux RSS ({url}): {e}")
        return None

# Endpoints API

# --- SYSTEME D'AUTHENTIFICATION ET SECURITE ---

@app.before_request
def check_auth():
    # Autoriser les requêtes OPTIONS (CORS) sans authentification
    if request.method == 'OPTIONS':
        return
        
    path = request.path
    # Seules les routes commençant par /api/ sont protégées
    if not path.startswith('/api/'):
        return
        
    # La route de login, de config et de vérification Nginx sont publiques
    if path in ('/api/login', '/api/config', '/api/verify-auth'):
        return
        
    if path == '/api/alerts/cron_check':
        provided_token = request.args.get('token')
        conn = get_db_connection()
        row = conn.execute("SELECT value FROM settings WHERE key = 'cron_token';").fetchone()
        conn.close()
        if row and row['value'] and row['value'] == provided_token:
            return
        return jsonify({'error': 'Unauthorized', 'message': 'Jeton de sécurité Cron invalide ou manquant.'}), 401
        
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized', 'message': 'Jeton de connexion requis.'}), 401
        
    token = auth_header.split(' ')[1]
    
    conn = get_db_connection()
    session = conn.execute(
        "SELECT username, expires_at FROM sessions WHERE token = ?;", 
        (token,)
    ).fetchone()
    conn.close()
    
    if not session:
        return jsonify({'error': 'Unauthorized', 'message': 'Session invalide ou expirée.'}), 401
        
    try:
        expires_at = datetime.fromisoformat(session['expires_at'])
        if expires_at < datetime.now():
            # Supprimer la session expirée
            conn = get_db_connection()
            conn.execute("DELETE FROM sessions WHERE token = ?;", (token,))
            conn.commit()
            conn.close()
            return jsonify({'error': 'Unauthorized', 'message': 'Session expirée.'}), 401
    except Exception:
        return jsonify({'error': 'Unauthorized', 'message': 'Format de session invalide.'}), 401

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' http://localhost:5000 http://localhost:8000;"
    
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        response.set_cookie('tracker_token', token, max_age=86400, path='/', samesite='Lax')

    return response

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        'enable_uptime_kuma': os.getenv('ENABLE_UPTIME_KUMA', 'false').lower() == 'true',
        'enable_opencve': os.getenv('OPENCVE_URL') is not None and os.getenv('OPENCVE_URL') != '',
        'enable_vigil365': os.getenv('ENABLE_VIGIL365', 'false').lower() == 'true'
    })

@app.route('/api/settings', methods=['GET'])
def get_settings():
    conn = get_db_connection()
    rows = conn.execute("SELECT key, value FROM settings;").fetchall()
    conn.close()
    
    settings_dict = {}
    for r in rows:
        settings_dict[r['key']] = r['value']
    return jsonify(settings_dict)

@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.json or {}
    conn = get_db_connection()
    for k, v in data.items():
        if k in ('teams_webhook_url', 'enable_notifications', 'notification_min_cvss', 'refresh_interval_hours', 'last_refresh_time', 'cron_token'):
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?);", (k, str(v)))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/settings/test_webhook', methods=['POST'])
def test_webhook():
    data = request.json or {}
    webhook_url = data.get('teams_webhook_url')
    if not webhook_url:
        conn = get_db_connection()
        row = conn.execute("SELECT value FROM settings WHERE key = 'teams_webhook_url';").fetchone()
        conn.close()
        if row:
            webhook_url = row['value']
            
    if not webhook_url:
        return jsonify({'error': 'URL de Webhook manquante ou non configurée.'}), 400
        
    success, error_msg = send_teams_notification(
        webhook_url=webhook_url,
        alert_title="[CVE / CVSS: 9.8] CVE-2026-99999 : Faille critique fictive de démonstration",
        alert_desc="Une vulnérabilité critique fictive a été détectée dans l'actif 'Test System'. Versions impactées : < 3.2.1. Cette notification confirme le bon fonctionnement du Webhook Teams.",
        alert_link="https://www.cve.org/",
        asset_name="Système de Test Herakles",
        asset_version="3.2.0",
        cve_id="CVE-2026-99999",
        cvss_score="9.8",
        priority="critical",
        pub_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        responsable="ADM (admin@example.com)"
    )
    
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': f"Échec de l'envoi de la notification Teams : {error_msg}"}), 500

@app.route('/api/alerts/cron_check', methods=['POST'])
def cron_check():
    conn = get_db_connection()
    settings_rows = conn.execute("SELECT key, value FROM settings;").fetchall()
    settings = {r['key']: r['value'] for r in settings_rows}
    
    refresh_interval_hours = 12.0
    try:
        refresh_interval_hours = float(settings.get('refresh_interval_hours', '12'))
    except Exception:
        pass
        
    last_refresh_time_str = settings.get('last_refresh_time', '')
    conn.close()
    
    now = datetime.now()
    
    if refresh_interval_hours > 0.0 and last_refresh_time_str:
        try:
            last_refresh = datetime.fromisoformat(last_refresh_time_str)
            elapsed = (now - last_refresh).total_seconds() / 3600.0
            if elapsed < refresh_interval_hours:
                return jsonify({
                    'status': 'skipped',
                    'reason': f"L'intervalle de {refresh_interval_hours}h n'est pas encore écoulé. Dernier refresh: {last_refresh_time_str} (il y a {elapsed:.2f}h)."
                })
        except Exception as e:
            print(f"Erreur lors du parsing de last_refresh_time : {e}")
            
    try:
        response_obj = refresh_alerts(notify=True)
        res_data = response_obj.get_json()
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f"Erreur lors de l'exécution du refresh d'alertes : {e}"
        }), 500
        
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('last_refresh_time', ?);", (now.isoformat(),))
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'last_refresh_time': now.isoformat(),
        'new_alerts_count': res_data.get('new_alerts_count', 0),
        'unreachable_urls': res_data.get('unreachable_urls', [])
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    
    if not username or not password:
        return jsonify({'error': 'Veuillez saisir un nom d\'utilisateur et un mot de passe.'}), 400
        
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?;", (username,)).fetchone()
    conn.close()
    
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Identifiants incorrects.'}), 401
        
    # Génération du jeton de session
    token = secrets.token_hex(32)
    # Expiration dans 24 heures
    expires_at = (datetime.now() + timedelta(hours=24)).isoformat()
    
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO sessions (token, username, expires_at) VALUES (?, ?, ?);",
        (token, username, expires_at)
    )
    conn.commit()
    conn.close()
    
    resp = make_response(jsonify({
        'success': True,
        'token': token,
        'username': username
    }))
    resp.set_cookie('tracker_token', token, max_age=86400, path='/', samesite='Lax')
    return resp

@app.route('/api/logout', methods=['POST'])
def logout():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        conn = get_db_connection()
        conn.execute("DELETE FROM sessions WHERE token = ?;", (token,))
        conn.commit()
        conn.close()
    resp = make_response(jsonify({'success': True}))
    resp.delete_cookie('tracker_token', path='/')
    return resp

@app.route('/api/verify-auth', methods=['GET', 'HEAD'])
def verify_auth():
    token = request.cookies.get('tracker_token')
    if not token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        else:
            token = request.args.get('token')

    if not token:
        return '', 401

    conn = get_db_connection()
    session = conn.execute(
        "SELECT username, expires_at FROM sessions WHERE token = ?;", 
        (token,)
    ).fetchone()
    conn.close()

    if not session:
        return '', 401

    try:
        expires_at = datetime.fromisoformat(session['expires_at'])
        if expires_at < datetime.now():
            return '', 401
    except Exception:
        return '', 401

    return '', 200

@app.route('/api/me', methods=['GET'])
def get_me():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'authenticated': False}), 401
        
    token = auth_header.split(' ')[1]
    conn = get_db_connection()
    session = conn.execute("SELECT username FROM sessions WHERE token = ?;", (token,)).fetchone()
    conn.close()
    
    if not session:
        return jsonify({'authenticated': False}), 401
        
    return jsonify({
        'authenticated': True,
        'username': session['username']
    })

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
    
    result = []
    for a in assets:
        a_dict = dict(a)
        urls = conn.execute("SELECT url FROM asset_urls WHERE asset_id = ? ORDER BY is_primary DESC, id ASC;", (a_dict['id'],)).fetchall()
        a_dict['urls'] = [u['url'] for u in urls]
        a_dict['tags'] = [t.strip() for t in (a_dict.get('tags') or '').split(',') if t.strip()]
        result.append(a_dict)
        
    conn.close()
    return jsonify(result)

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
    
    # Gestion des URLs multiples et validation de sécurité
    urls = data.get('urls', [])
    if isinstance(urls, str):
        urls = [urls]
    urls_clean = []
    for u in urls:
        u_strip = u.strip()
        if u_strip:
            val_u = validate_and_clean_url(u_strip)
            if not val_u:
                return jsonify({'error': f'L\'URL "{u_strip}" est invalide ou interdite pour des raisons de sécurité. Seuls les protocoles HTTP/HTTPS (publics) et opencve:// sont autorisés.'}), 400
            urls_clean.append(val_u)
    urls = urls_clean
    url_rss = urls[0] if urls else None
    
    # Gestion des tags
    tags = data.get('tags', '')
    if isinstance(tags, list):
        tags = [t.strip() for t in tags if t and t.strip()]
        tags = ', '.join(tags)
    elif isinstance(tags, str):
        tags = ', '.join([t.strip() for t in tags.split(',') if t.strip()])
    else:
        tags = ''
        
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
            INSERT INTO assets (nom_produit, fournisseur, version_actuelle, type_deploiement, machine_hebergement, type_licence, date_expiration, url_rss, responsable, entites, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (nom_produit, fournisseur, version_actuelle, type_deploiement, machine_hebergement, type_licence, date_expiration, url_rss, responsable, entites, tags))
        asset_id = cursor.lastrowid
        
        # Insérer les URLs dans la table de jointure asset_urls
        for idx, u in enumerate(urls):
            is_prim = 1 if idx == 0 else 0
            conn.execute("INSERT INTO asset_urls (asset_id, url, is_primary) VALUES (?, ?, ?);", (asset_id, u, is_prim))
            
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({'error': f'Erreur de base de données : {str(e)}'}), 500

    conn.close()
    return jsonify({'id': asset_id, 'success': True}), 201

@app.route('/api/assets/<int:asset_id>/duplicate', methods=['POST'])
def duplicate_asset(asset_id):
    conn = get_db_connection()
    
    # Récupérer l'actif source
    asset = conn.execute("SELECT * FROM assets WHERE id = ?;", (asset_id,)).fetchone()
    if not asset:
        conn.close()
        return jsonify({'error': 'Actif introuvable'}), 404
    
    asset = dict(asset)
    urls = conn.execute(
        "SELECT url, is_primary FROM asset_urls WHERE asset_id = ? ORDER BY is_primary DESC, id ASC;",
        (asset_id,)
    ).fetchall()
    
    try:
        cursor = conn.execute("""
            INSERT INTO assets (nom_produit, fournisseur, version_actuelle, type_deploiement,
                machine_hebergement, type_licence, date_expiration, url_rss,
                responsable, entites, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            asset['nom_produit'] + ' (copie)',
            asset['fournisseur'],
            asset['version_actuelle'],
            asset['type_deploiement'],
            asset['machine_hebergement'],
            asset['type_licence'],
            asset['date_expiration'],
            asset['url_rss'],
            asset['responsable'],
            asset['entites'],
            asset['tags'],
        ))
        new_id = cursor.lastrowid
        
        for url_row in urls:
            conn.execute(
                "INSERT INTO asset_urls (asset_id, url, is_primary) VALUES (?, ?, ?);",
                (new_id, url_row['url'], url_row['is_primary'])
            )
        
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({'error': f'Erreur de duplication : {str(e)}'}), 500
    
    conn.close()
    return jsonify({'id': new_id, 'success': True}), 201


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
    
    # Gestion des URLs multiples et validation de sécurité
    urls = data.get('urls', [])
    if isinstance(urls, str):
        urls = [urls]
    urls_clean = []
    for u in urls:
        u_strip = u.strip()
        if u_strip:
            val_u = validate_and_clean_url(u_strip)
            if not val_u:
                return jsonify({'error': f'L\'URL "{u_strip}" est invalide ou interdite pour des raisons de sécurité. Seuls les protocoles HTTP/HTTPS (publics) et opencve:// sont autorisés.'}), 400
            urls_clean.append(val_u)
    urls = urls_clean
    url_rss = urls[0] if urls else None
    
    # Gestion des tags
    tags = data.get('tags', '')
    if isinstance(tags, list):
        tags = [t.strip() for t in tags if t and t.strip()]
        tags = ', '.join(tags)
    elif isinstance(tags, str):
        tags = ', '.join([t.strip() for t in tags.split(',') if t.strip()])
    else:
        tags = ''
        
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
                machine_hebergement = ?, type_licence = ?, date_expiration = ?, url_rss = ?, responsable = ?, entites = ?, tags = ?
            WHERE id = ?;
        """, (nom_produit, fournisseur, version_actuelle, type_deploiement, machine_hebergement, type_licence, date_expiration, url_rss, responsable, entites, tags, asset_id))
        
        # Mettre à jour les URLs multiples (supprimer et insérer)
        conn.execute("DELETE FROM asset_urls WHERE asset_id = ?;", (asset_id,))
        for idx, u in enumerate(urls):
            is_prim = 1 if idx == 0 else 0
            conn.execute("INSERT INTO asset_urls (asset_id, url, is_primary) VALUES (?, ?, ?);", (asset_id, u, is_prim))
            
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

@app.route('/api/import/excel', methods=['POST'])
def import_excel():
    data = request.json or {}
    team_data = data.get('team', [])
    assets_data = data.get('assets', [])
    
    conn = get_db_connection()
    
    team_added = 0
    team_updated = 0
    assets_added = 0
    assets_updated = 0
    errors = []

    # 1. Traitement des membres d'équipe
    for idx, member in enumerate(team_data, start=1):
        trigramme = str(member.get('trigramme') or '').strip().upper()
        email = str(member.get('email') or '').strip()
        
        if not trigramme or not email:
            errors.append(f"Équipe ligne {idx} : Trigramme ou email manquant.")
            continue
            
        if len(trigramme) != 3:
            errors.append(f"Équipe ligne {idx} ({trigramme}) : Le trigramme doit comporter exactement 3 lettres.")
            continue
            
        existing = conn.execute("SELECT email FROM team WHERE trigramme = ?;", (trigramme,)).fetchone()
        if existing:
            conn.execute("UPDATE team SET email = ? WHERE trigramme = ?;", (email, trigramme))
            team_updated += 1
        else:
            conn.execute("INSERT INTO team (trigramme, email) VALUES (?, ?);", (trigramme, email))
            team_added += 1

    # Récupérer la liste à jour de tous les trigrammes valides
    valid_team = {row['trigramme'] for row in conn.execute("SELECT trigramme FROM team;").fetchall()}

    # 2. Traitement des actifs
    for idx, a in enumerate(assets_data, start=1):
        nom_produit = str(a.get('nom_produit') or '').strip()
        fournisseur = str(a.get('fournisseur') or '').strip() or None
        version_actuelle = str(a.get('version_actuelle') or '').strip()
        type_deploiement = str(a.get('type_deploiement') or '').strip()
        machine_hebergement = str(a.get('machine_hebergement') or '').strip() or None
        type_licence = str(a.get('type_licence') or 'Perpétuelle').strip()
        date_expiration = str(a.get('date_expiration') or '').strip() or None
        responsable = str(a.get('responsable') or '').strip().upper()

        entites = a.get('entites') or 'Groupe'
        if isinstance(entites, list):
            entites = ', '.join([str(e).strip() for e in entites if str(e).strip()])
        else:
            entites = str(entites).strip()
        if not entites:
            entites = 'Groupe'

        tags = a.get('tags') or ''
        if isinstance(tags, list):
            tags = ', '.join([str(t).strip() for t in tags if str(t).strip()])
        else:
            tags = ', '.join([str(t).strip() for t in str(tags).split(',') if str(t).strip()])

        raw_urls = a.get('urls') or a.get('url_rss') or []
        if isinstance(raw_urls, str):
            raw_urls = [u.strip() for u in raw_urls.replace('\n', ',').split(',') if u.strip()]
        urls_clean = []
        for u in raw_urls:
            u_str = str(u).strip()
            if u_str:
                val_u = validate_and_clean_url(u_str)
                if val_u and val_u not in urls_clean:
                    urls_clean.append(val_u)
        url_rss = urls_clean[0] if urls_clean else None

        # Validations obligatoires
        if not nom_produit:
            errors.append(f"Actif ligne {idx} : Nom du produit obligatoire.")
            continue
        if not version_actuelle:
            errors.append(f"Actif ligne {idx} ({nom_produit}) : Version actuelle obligatoire.")
            continue
        if not type_deploiement:
            errors.append(f"Actif ligne {idx} ({nom_produit}) : Type de déploiement obligatoire.")
            continue
        if not responsable:
            errors.append(f"Actif ligne {idx} ({nom_produit}) : Responsable (trigramme) obligatoire.")
            continue
        if responsable not in valid_team:
            errors.append(f"Actif ligne {idx} ({nom_produit}) : Responsable '{responsable}' inconnu dans l'équipe.")
            continue

        if type_deploiement == 'Self-hosted' and not machine_hebergement:
            errors.append(f"Actif ligne {idx} ({nom_produit}) : Machine/Serveur requis pour un déploiement Self-hosted.")
            continue
        if type_licence == 'Limitée' and not date_expiration:
            errors.append(f"Actif ligne {idx} ({nom_produit}) : Date d'expiration requise pour une licence Limitée.")
            continue

        # Vérifier si l'actif existe déjà (par nom_produit)
        existing_asset = conn.execute("SELECT id FROM assets WHERE LOWER(nom_produit) = LOWER(?);", (nom_produit,)).fetchone()

        try:
            if existing_asset:
                asset_id = existing_asset['id']
                conn.execute("""
                    UPDATE assets
                    SET nom_produit = ?, fournisseur = ?, version_actuelle = ?, type_deploiement = ?,
                        machine_hebergement = ?, type_licence = ?, date_expiration = ?, url_rss = ?,
                        responsable = ?, entites = ?, tags = ?
                    WHERE id = ?;
                """, (nom_produit, fournisseur, version_actuelle, type_deploiement,
                      machine_hebergement, type_licence, date_expiration, url_rss,
                      responsable, entites, tags, asset_id))

                conn.execute("DELETE FROM asset_urls WHERE asset_id = ?;", (asset_id,))
                for u_idx, u_val in enumerate(urls_clean):
                    conn.execute("INSERT INTO asset_urls (asset_id, url, is_primary) VALUES (?, ?, ?);",
                                 (asset_id, u_val, 1 if u_idx == 0 else 0))
                assets_updated += 1
            else:
                cursor = conn.execute("""
                    INSERT INTO assets (nom_produit, fournisseur, version_actuelle, type_deploiement,
                                        machine_hebergement, type_licence, date_expiration, url_rss,
                                        responsable, entites, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (nom_produit, fournisseur, version_actuelle, type_deploiement,
                      machine_hebergement, type_licence, date_expiration, url_rss,
                      responsable, entites, tags))
                asset_id = cursor.lastrowid
                for u_idx, u_val in enumerate(urls_clean):
                    conn.execute("INSERT INTO asset_urls (asset_id, url, is_primary) VALUES (?, ?, ?);",
                                 (asset_id, u_val, 1 if u_idx == 0 else 0))
                assets_added += 1
        except Exception as e:
            errors.append(f"Actif ligne {idx} ({nom_produit}) : Erreur SQL {str(e)}")

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'team_added': team_added,
        'team_updated': team_updated,
        'assets_added': assets_added,
        'assets_updated': assets_updated,
        'errors': errors
    })


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
    data = request.get_json(silent=True) or {}
    resolved_by = data.get('resolved_by') or data.get('resolveur')

    conn = get_db_connection()
    # Récupérer la version actuelle et le responsable de l'actif associé à cette alerte
    asset_row = conn.execute("""
        SELECT asst.version_actuelle, asst.responsable 
        FROM assets asst
        JOIN alerts al ON al.asset_id = asst.id
        WHERE al.id = ?;
    """, (alert_id,)).fetchone()
    
    version_actuelle = asset_row['version_actuelle'] if asset_row else None
    if not resolved_by and asset_row:
        resolved_by = asset_row['responsable']

    conn.execute("UPDATE alerts SET resolved = 1, resolved_at_version = ?, resolved_by = ? WHERE id = ?;", (version_actuelle, resolved_by, alert_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/alerts/resolved', methods=['GET'])
def get_resolved_alerts():
    conn = get_db_connection()
    alerts_raw = conn.execute("""
        SELECT al.*, asst.nom_produit as nom_produit, asst.responsable as responsable, asst.version_actuelle as version_actuelle
        FROM alerts al
        JOIN assets asst ON al.asset_id = asst.id
        WHERE al.resolved = 1
        ORDER BY al.id DESC;
    """).fetchall()
    conn.close()
    
    res = [dict(a) for a in alerts_raw]
    return jsonify(res)

@app.route('/api/alerts/reactivate/<int:alert_id>', methods=['POST'])
def reactivate_alert(alert_id):
    conn = get_db_connection()
    conn.execute("UPDATE alerts SET resolved = 0, resolved_at_version = NULL, resolved_by = NULL WHERE id = ?;", (alert_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/alerts/resolve-asset/<int:asset_id>', methods=['POST'])
def resolve_asset_alerts(asset_id):
    data = request.get_json(silent=True) or {}
    new_version = data.get('new_version')
    resolved_by = data.get('resolved_by') or data.get('resolveur')

    conn = get_db_connection()
    
    # Si non fourni, tenter de le trouver dans les alertes actives de cet actif
    if not new_version:
        alerts = conn.execute("""
            SELECT al.title, al.description 
            FROM alerts al 
            WHERE al.asset_id = ? AND al.resolved = 0;
        """, (asset_id,)).fetchall()
        
        parsed_versions = []
        for al in alerts:
            title = al['title'] or ''
            description = al['description'] or ''
            full_text = f"{title} \n {description}"
            
            # 1. Tenter d'extraire depuis le titre de release (ex: "v0.46.0")
            title_clean = title.strip()
            # Supprimer le 'v' initial pour la validation regex
            title_test = title_clean[1:] if title_clean.lower().startswith('v') else title_clean
            version_pattern = r'^\d+(?:\.\d+)+(?:-\d+)?$'
            if re.match(version_pattern, title_test):
                ver_obj = parse_version_safe(title_clean)
                if ver_obj:
                    parsed_versions.append((ver_obj, title_clean))
            
            # 2. Tenter d'extraire depuis un pattern de correctif (ex: "fixed in 5.4.7")
            correction_patterns = [
                r'(?:upgrade|update|corrige|fix|patch)\s+(?:to|in|à|dans)?\s*(?:version|v)?\s*(\d+\.\d+\.\d+(?:\.\d+)?)',
                r'fixed\s+in\s*(?:version|v)?\s*(\d+\.\d+\.\d+(?:\.\d+)?)',
                r'corrigé\s+dans\s+la\s+version\s*(\d+\.\d+\.\d+(?:\.\d+)?)'
            ]
            for pat in correction_patterns:
                match = re.search(pat, full_text, re.IGNORECASE)
                if match:
                    fixed_ver_str = match.group(1)
                    ver_obj = parse_version_safe(fixed_ver_str)
                    if ver_obj:
                        parsed_versions.append((ver_obj, fixed_ver_str))
                        
            # 3. Tenter d'extraire depuis le titre Joomla (ex: "Mise à jour disponible : Version 2.9.71 disponible")
            joomla_match = re.search(r'Mise à jour disponible\s*:\s*Version\s+([^\s]+)\s+disponible', title)
            if joomla_match:
                ver_str = joomla_match.group(1).strip()
                ver_obj = parse_version_safe(ver_str)
                if ver_obj:
                    parsed_versions.append((ver_obj, ver_str))
                        
        # Prendre la version sémantique la plus élevée trouvée
        if parsed_versions:
            parsed_versions.sort(key=lambda x: x[0], reverse=True)
            new_version = parsed_versions[0][1]
            
    # Récupérer l'ancienne version, le nom du produit et le responsable par défaut
    asset = conn.execute("SELECT nom_produit, version_actuelle, responsable FROM assets WHERE id = ?;", (asset_id,)).fetchone()
    ancienne_version = asset['version_actuelle'] if asset else 'N/A'
    nom_produit = asset['nom_produit'] if asset else 'Inconnu'
    if not resolved_by and asset:
        resolved_by = asset['responsable']

    # Mettre à jour la version de l'actif
    if new_version:
        clean_ver = new_version.strip()
        if clean_ver.lower().startswith('v'):
            clean_ver = clean_ver[1:]
        conn.execute("UPDATE assets SET version_actuelle = ? WHERE id = ?;", (clean_ver, asset_id))
        
        # Consigner l'historique si la version a effectivement changé
        if clean_ver != ancienne_version:
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            conn.execute("""
                INSERT INTO update_logs (asset_id, nom_produit, ancienne_version, nouvelle_version, date_maj, resolved_by)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (asset_id, nom_produit, ancienne_version, clean_ver, now_str, resolved_by))
        
    # Récupérer la version de l'actif après mise à jour
    updated_asset = conn.execute("SELECT version_actuelle FROM assets WHERE id = ?;", (asset_id,)).fetchone()
    updated_ver = updated_asset['version_actuelle'] if updated_asset else None
    
    conn.execute("UPDATE alerts SET resolved = 1, resolved_at_version = ?, resolved_by = ? WHERE asset_id = ? AND resolved = 0;", (updated_ver, resolved_by, asset_id))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'updated_version': new_version
    })

def fetch_feed_for_asset_url(asset_dict, url, is_primary):
    triggered_alerts = []
    xml_data = None
    version_actuelle = asset_dict['version_actuelle']

    if url.lower().startswith('opencve://'):
        is_joomla = False
    else:
        try:
            clean_url = validate_and_clean_url(url)
            if not clean_url:
                print(f"URL de flux RSS bloquée pour des raisons de sécurité : {url}")
                return url, []
                
            req = urllib.request.Request(
                clean_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) herakles-it-tracker/1.0'}
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                xml_data = response.read()
        except Exception as e:
            print(f"Erreur de récupération de l'URL ({url}): {e}")
            return url, []

        is_joomla = url.split('?')[0].lower().endswith('.xml')
        root = None
        if not is_joomla:
            try:
                root = ET.fromstring(xml_data)
                root_tag = root.tag.split('}')[-1]
                if root_tag in ('updates', 'update') or root.find('.//updates') is not None or root.find('.//update') is not None:
                    is_joomla = True
            except Exception:
                pass

    if is_joomla:
        if root is None:
            try:
                root = ET.fromstring(xml_data)
            except Exception as e:
                print(f"Erreur lors du parsing du fichier XML Joomla ({url}): {e}")
                return None, []

        updates_list = []
        if root.tag.split('}')[-1] == 'update':
            updates_list.append(root)
        else:
            def find_all_updates(elem):
                res = []
                tag = elem.tag.split('}')[-1]
                if tag == 'update':
                    res.append(elem)
                else:
                    for child in elem:
                        res.extend(find_all_updates(child))
                return res
            updates_list = find_all_updates(root)

        best_update = None
        best_version_obj = None

        for upd in updates_list:
            ver_str = None
            for child in upd:
                if child.tag.split('}')[-1] == 'version' and child.text:
                    ver_str = child.text.strip()
                    break
            if ver_str:
                ver_obj = parse_version_safe(ver_str)
                if ver_obj:
                    if best_version_obj is None or ver_obj > best_version_obj:
                        best_version_obj = ver_obj
                        best_update = (ver_str, upd)

        if best_update:
            xml_version, upd_elem = best_update
            xml_ver = best_version_obj
            asset_ver = parse_version_safe(version_actuelle)

            if xml_ver and asset_ver and xml_ver > asset_ver:
                title = f"Mise à jour disponible : Version {xml_version} disponible (Actuellement en {version_actuelle})"
                
                xml_infourl = None
                for child in upd_elem:
                    if child.tag.split('}')[-1] == 'infourl' and child.text:
                        xml_infourl = child.text.strip()
                        break
                        
                link = xml_infourl if xml_infourl else url
                pub_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

                triggered_alert_for_url = {
                    'title': title,
                    'description': f"Une nouvelle version {xml_version} est disponible pour l'actif {asset_dict['nom_produit']}.",
                    'link': link,
                    'pub_date': pub_date,
                    'trigger_url': url,
                    'is_secondary': 0 if is_primary else 1
                }
                triggered_alerts.append(triggered_alert_for_url)

    else:
        # RSS Feed
        feed_items = fetch_rss_feed(url, xml_data=xml_data)
        if feed_items is not None:
            for item in feed_items:
                title = item['title']
                desc = item.get('description', '')
                link = item['link']
                pub_date = item['pub_date']
                extracted_ver = item.get('extracted_version')
                
                if extracted_ver and extracted_ver.lower() not in title.lower():
                    title = f"{title} ({extracted_ver})"
                    
                temp_alert = {
                    'title': title,
                    'description': desc,
                    'version_actuelle': version_actuelle,
                    'extracted_version': extracted_ver
                }
                status, priority, status_text, affected_versions = analyze_alert(temp_alert)
                
                if status != 'hide':
                    triggered_alerts.append({
                        'title': title,
                        'description': desc,
                        'link': link,
                        'pub_date': pub_date,
                        'trigger_url': url,
                        'is_secondary': 0 if is_primary else 1
                    })

    return None, triggered_alerts

@app.route('/api/alerts/refresh', methods=['POST'])
def refresh_alerts(notify=False):
    conn = get_db_connection()
    settings_rows = conn.execute("SELECT key, value FROM settings;").fetchall()
    settings = {r['key']: r['value'] for r in settings_rows}
    
    notify_enabled = settings.get('enable_notifications', 'false').lower() == 'true'
    teams_webhook_url = settings.get('teams_webhook_url', '')
    try:
        notification_min_cvss = float(settings.get('notification_min_cvss', '7.0'))
    except Exception:
        notification_min_cvss = 7.0
        
    assets = conn.execute("""
        SELECT a.id, a.nom_produit, a.version_actuelle, a.responsable, t.email as email_responsable
        FROM assets a
        LEFT JOIN team t ON a.responsable = t.trigramme;
    """).fetchall()
    
    tasks = []
    for asset in assets:
        asset_dict = dict(asset)
        asset_id = asset_dict['id']
        urls_rows = conn.execute("SELECT url, is_primary FROM asset_urls WHERE asset_id = ? ORDER BY is_primary DESC, id ASC;", (asset_id,)).fetchall()
        for u_row in urls_rows:
            tasks.append((asset_dict, u_row['url'], u_row['is_primary']))
            
    unreachable_urls = []
    new_alerts_count = 0
    results = []
    
    if tasks:
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_task = {
                executor.submit(fetch_feed_for_asset_url, asset_dict, url, is_primary): (asset_dict, url, is_primary)
                for asset_dict, url, is_primary in tasks
            }
            for future in as_completed(future_to_task):
                asset_dict, url, is_primary = future_to_task[future]
                try:
                    unreach, triggered = future.result()
                    if unreach:
                        unreachable_urls.append(unreach)
                    results.append({
                        'asset': asset_dict,
                        'url': url,
                        'is_primary': is_primary,
                        'triggered_alerts': triggered
                    })
                except Exception as e:
                    print(f"Erreur lors de l'exécution parallèle du flux ({url}): {e}")
                    unreachable_urls.append(url)

    for res_item in results:
        asset = res_item['asset']
        asset_id = asset['id']
        version_actuelle = asset['version_actuelle']
        url = res_item['url']
        is_primary = res_item['is_primary']
        triggered_alerts = res_item['triggered_alerts']

        # Gérer la résolution automatique des alertes obsolètes et le maintien des alertes encore vulnérables
        existing_active = conn.execute("""
            SELECT id, title, description FROM alerts
            WHERE asset_id = ? AND trigger_url = ? AND resolved = 0;
        """, (asset_id, url)).fetchall()
        
        active_titles = {a['title'] for a in triggered_alerts}
        
        for ea in existing_active:
            if ea['title'] not in active_titles:
                ea_title = ea['title']
                ea_extracted_ver = None
                if '(' in ea_title and ea_title.endswith(')'):
                    ver_part = ea_title.split('(')[-1][:-1]
                    if ver_part.lower().startswith('v'):
                        ver_part = ver_part[1:]
                    ea_extracted_ver = ver_part
                
                temp_alert = {
                    'title': ea['title'],
                    'description': ea['description'],
                    'version_actuelle': version_actuelle,
                    'extracted_version': ea_extracted_ver
                }
                status, priority, status_text, affected_versions = analyze_alert(temp_alert)
                if status == 'hide':
                    conn.execute("""
                        UPDATE alerts 
                        SET resolved = 1, resolved_at_version = ?
                        WHERE id = ?;
                    """, (version_actuelle, ea['id']))
        
        for a in triggered_alerts:
            existing = conn.execute("""
                SELECT id FROM alerts 
                WHERE asset_id = ? AND trigger_url = ? AND title = ? AND resolved = 0;
            """, (asset_id, url, a['title'])).fetchone()
            
            if existing:
                conn.execute("""
                    UPDATE alerts 
                    SET description = ?, link = ?, pub_date = ?, is_secondary = ?
                    WHERE id = ?;
                """, (a['description'], a['link'], a['pub_date'], a['is_secondary'], existing['id']))
            else:
                existing_resolved = conn.execute("""
                    SELECT id, resolved_at_version FROM alerts 
                    WHERE asset_id = ? AND trigger_url = ? AND title = ? AND resolved = 1;
                """, (asset_id, url, a['title'])).fetchone()
                
                is_new_alert = False
                if existing_resolved:
                    resolved_at_ver = existing_resolved['resolved_at_version']
                    if resolved_at_ver is not None and resolved_at_ver != version_actuelle:
                        conn.execute("""
                            UPDATE alerts 
                            SET resolved = 0, description = ?, link = ?, pub_date = ?, is_secondary = ?
                            WHERE id = ?;
                        """, (a['description'], a['link'], a['pub_date'], a['is_secondary'], existing_resolved['id']))
                        is_new_alert = True
                    elif resolved_at_ver is None:
                        conn.execute("""
                            UPDATE alerts 
                            SET resolved_at_version = ?
                            WHERE id = ?;
                        """, (version_actuelle, existing_resolved['id']))
                else:
                    conn.execute("""
                        INSERT INTO alerts (asset_id, title, description, link, pub_date, resolved, trigger_url, is_secondary)
                        VALUES (?, ?, ?, ?, ?, 0, ?, ?);
                    """, (asset_id, a['title'], a['description'], a['link'], a['pub_date'], url, a['is_secondary']))
                    new_alerts_count += 1
                    is_new_alert = True
                    
                if is_new_alert and notify and notify_enabled and teams_webhook_url:
                    # Analyser la criticité
                    temp_alert = {
                        'title': a['title'],
                        'description': a['description'],
                        'version_actuelle': version_actuelle,
                        'extracted_version': None
                    }
                    status, priority, status_text, affected_versions = analyze_alert(temp_alert)
                    
                    # Vérifier si c'est une CVE et extraire le score CVSS
                    cvss_score = None
                    cvss_match = re.search(r'\[CVE / CVSS:\s*(\d+(?:\.\d+)?)\]', a['title'])
                    if cvss_match:
                        cvss_score = float(cvss_match.group(1))
                    
                    is_cve = bool(re.search(r'\b(CVE-\d{4}-\d{4,})\b', a['title']))
                    
                    should_notify = False
                    if cvss_score is not None:
                        if cvss_score >= notification_min_cvss:
                            should_notify = True
                    else:
                        if is_cve:
                            should_notify = True
                        elif priority in ('critical', 'high'):
                            should_notify = True
                            
                    if should_notify:
                        cve_id = None
                        cve_match = re.search(r'\b(CVE-\d{4}-\d{4,})\b', a['title'])
                        if cve_match:
                            cve_id = cve_match.group(1)
                            
                        resp_trigramme = asset['responsable'] if 'responsable' in asset.keys() and asset['responsable'] else ''
                        resp_email = asset['email_responsable'] if 'email_responsable' in asset.keys() and asset['email_responsable'] else ''
                        resp_str = f"{resp_trigramme} ({resp_email})" if (resp_trigramme and resp_email) else (resp_trigramme or None)

                        send_teams_notification(
                            webhook_url=teams_webhook_url,
                            alert_title=a['title'],
                            alert_desc=a['description'],
                            alert_link=a['link'],
                            asset_name=asset['nom_produit'],
                            asset_version=version_actuelle,
                            cve_id=cve_id,
                            cvss_score=cvss_score,
                            priority=priority,
                            pub_date=a['pub_date'],
                            responsable=resp_str
                        )
                
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

@app.route('/api/update-logs', methods=['GET'])
def get_update_logs():
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM update_logs ORDER BY date_maj DESC, id DESC;").fetchall()
    conn.close()
    return jsonify([dict(l) for l in logs])

@app.route('/api/update-logs/revert/<int:log_id>', methods=['POST'])
def revert_update_log(log_id):
    conn = get_db_connection()
    log = conn.execute("SELECT * FROM update_logs WHERE id = ?;", (log_id,)).fetchone()
    if not log:
        conn.close()
        return jsonify({'error': 'Log non trouvé'}), 404
        
    asset_id = log['asset_id']
    ancienne_version = log['ancienne_version']
    nouvelle_version = log['nouvelle_version']
    
    # 1. Remettre l'actif à son ancienne version
    conn.execute("UPDATE assets SET version_actuelle = ? WHERE id = ?;", (ancienne_version, asset_id))
    
    # 2. Réactiver les alertes qui avaient été résolues à cette nouvelle version
    conn.execute("""
        UPDATE alerts 
        SET resolved = 0, resolved_at_version = NULL, resolved_by = NULL 
        WHERE asset_id = ? AND resolved_at_version = ?;
    """, (asset_id, nouvelle_version))
    
    # 3. Supprimer le log de mise à jour
    conn.execute("DELETE FROM update_logs WHERE id = ?;", (log_id,))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

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
    
    # Création incrémentale et migrations de la base de données
    try:
        conn = sqlite3.connect(DB_PATH)
        # 1. Table update_logs
        conn.execute("""
        CREATE TABLE IF NOT EXISTS update_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            nom_produit TEXT NOT NULL,
            ancienne_version TEXT NOT NULL,
            nouvelle_version TEXT NOT NULL,
            date_maj TEXT NOT NULL,
            resolved_by TEXT,
            FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
        );
        """)
        
        # 2. Table asset_urls
        conn.execute("""
        CREATE TABLE IF NOT EXISTS asset_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            is_primary INTEGER DEFAULT 0,
            FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
        );
        """)

        # 3. Migration des url_rss existantes vers asset_urls
        cursor = conn.execute("SELECT id, url_rss FROM assets WHERE url_rss IS NOT NULL AND url_rss != '';")
        rows = cursor.fetchall()
        for r in rows:
            asset_id = r[0]
            url = r[1]
            check = conn.execute("SELECT 1 FROM asset_urls WHERE asset_id = ? AND url = ?;", (asset_id, url)).fetchone()
            if not check:
                conn.execute("INSERT INTO asset_urls (asset_id, url, is_primary) VALUES (?, ?, 1);", (asset_id, url))
        
        # 4. Colonnes alerts et update_logs
        try:
            conn.execute("ALTER TABLE alerts ADD COLUMN trigger_url TEXT;")
        except sqlite3.OperationalError:
            pass
            
        try:
            conn.execute("ALTER TABLE alerts ADD COLUMN is_secondary INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass
            
        try:
            conn.execute("ALTER TABLE alerts ADD COLUMN resolved_at_version TEXT;")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE alerts ADD COLUMN resolved_by TEXT;")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE update_logs ADD COLUMN resolved_by TEXT;")
        except sqlite3.OperationalError:
            pass
            
        # 5. Colonne tags pour assets
        try:
            conn.execute("ALTER TABLE assets ADD COLUMN tags TEXT DEFAULT '';")
        except sqlite3.OperationalError:
            pass
            
        # 6. Table users
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        """)
        
        # 7. Table sessions
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        """)
        
        # 7.5. Table settings
        conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        
        # Seeding des paramètres par défaut
        default_settings = {
            'teams_webhook_url': '',
            'enable_notifications': 'false',
            'notification_min_cvss': '7.0',
            'refresh_interval_hours': '12',
            'last_refresh_time': '',
            'cron_token': secrets.token_hex(16)
        }
        for k, v in default_settings.items():
            existing_setting = conn.execute("SELECT 1 FROM settings WHERE key = ?;", (k,)).fetchone()
            if not existing_setting:
                conn.execute("INSERT INTO settings (key, value) VALUES (?, ?);", (k, v))
        
        # 8. Synchronisation/création de l'administrateur
        from werkzeug.security import generate_password_hash
        admin_user = os.getenv('TRACKER_ADMIN_USER', 'admin')
        admin_password = os.getenv('TRACKER_ADMIN_PASSWORD')
        if not admin_password:
            # Générer un mot de passe aléatoire sécurisé si non configuré
            import secrets as _secrets
            admin_password = _secrets.token_urlsafe(24)
            print(f"[AVERTISSEMENT] TRACKER_ADMIN_PASSWORD non défini. Mot de passe aléatoire généré pour '{admin_user}'.")
            print(f"[AVERTISSEMENT] Définissez TRACKER_ADMIN_PASSWORD dans votre fichier .env pour fixer ce mot de passe.")
        password_hash = generate_password_hash(admin_password)
        
        # On vérifie si l'admin existe
        existing = conn.execute("SELECT id, password_hash FROM users WHERE username = ?;", (admin_user,)).fetchone()
        if not existing:
            conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?);", (admin_user, password_hash))
            print(f"Compte administrateur créé : {admin_user}")
        else:
            conn.execute("UPDATE users SET password_hash = ? WHERE username = ?;", (password_hash, admin_user))
            print(f"Compte administrateur synchronisé avec l'environnement : {admin_user}")
            
        conn.commit()
        conn.close()
        print("Mise à jour et migration de la base de données terminées avec succès.")
    except Exception as e:
        print(f"Erreur lors de la mise à jour/migration de la base de données : {e}")
        
    app.run(host='0.0.0.0', port=5000, debug=True)
