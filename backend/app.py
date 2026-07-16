from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, date
import re
import json
import base64
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
    
    # Détection de score CVSS dans le titre (ex: "[CVE / CVSS: 9.8] CVE-2024-25140 - ...")
    cvss_match = re.search(r'\[CVE / CVSS:\s*(\d+(?:\.\d+)?)\]', title)
    if cvss_match:
        cvss_score = float(cvss_match.group(1))
        
        # Déterminer la priorité et le libellé de statut
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
                            if part.startswith('<=') or part.startswith('&lt;='):
                                v_str = part.replace('<=', '').replace('&lt;=', '').strip()
                                v = parse_version_safe(v_str)
                                if asset_ver and v and asset_ver <= v:
                                    part_matched = True
                            elif part.startswith('<') or part.startswith('&lt;'):
                                v_str = part.replace('<', '').replace('&lt;', '').strip()
                                v = parse_version_safe(v_str)
                                if asset_ver and v and asset_ver < v:
                                    part_matched = True
                            elif part.startswith('>=') or part.startswith('&gt;='):
                                v_str = part.replace('>=', '').replace('&gt;=', '').strip()
                                v = parse_version_safe(v_str)
                                if asset_ver and v and asset_ver >= v:
                                    part_matched = True
                            elif part.startswith('>') or part.startswith('&gt;'):
                                v_str = part.replace('>', '').replace('&gt;', '').strip()
                                v = parse_version_safe(v_str)
                                if asset_ver and v and asset_ver > v:
                                    part_matched = True
                            else:
                                if part == version_actuelle:
                                    part_matched = True
                                else:
                                    v = parse_version_safe(part)
                                    if asset_ver and v and asset_ver == v:
                                        part_matched = True
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
                                if asset_ver and v_min and v_max and v_min <= asset_ver <= v_max:
                                    part_matched = True
                            else:
                                if part == version_actuelle:
                                    part_matched = True
                                else:
                                    v = parse_version_safe(part)
                                    if asset_ver and v and asset_ver == v:
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

DB_PATH = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'database.db'))
# S'assurer que le dossier parent de la base existe
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    try:
        os.makedirs(db_dir, exist_ok=True)
    except Exception as e:
        print(f"Impossible de créer le dossier de base de données {db_dir} : {e}")

CERT_FR_FEED_URL = "https://www.cert.ssi.gouv.fr/feed/"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# Helper: Récupération des vulnérabilités depuis l'API REST d'OpenCVE
def fetch_opencve_feed(url):
    opencve_url = os.getenv('OPENCVE_URL', 'http://host.docker.internal:8000').rstrip('/')
    opencve_user = os.getenv('OPENCVE_USER', 'admin')
    opencve_password = os.getenv('OPENCVE_PASSWORD', 'admin')
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
        with urllib.request.urlopen(req, timeout=4) as response:
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

    # Filtrer les candidats
    norm_vendor = normalize_name(vendor)
    norm_product = normalize_name(product)
    
    filtered_results = []
    
    for cve_id, cve_sum in candidates.items():
        try:
            detail_url = f"{opencve_url}/api/cve/{cve_id}"
            detail_data_bytes = perform_request(detail_url)
            cve_detail = json.loads(detail_data_bytes)
        except Exception as e_detail:
            print(f"Erreur de récupération détails pour {cve_id} (fallback): {e_detail}")
            continue
            
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
            # On conserve le detail de la CVE dans l'objet pour éviter un second fetch en dessous
            cve_sum['_cached_detail'] = cve_detail
            filtered_results.append(cve_sum)

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

# Helper: Parseur RSS générique et robuste
def fetch_rss_feed(url, xml_data=None):
    if url.lower().startswith('opencve://'):
        return fetch_opencve_feed(url)
    try:
        if xml_data is None:
            if url.lower().startswith('file://'):
                with urllib.request.urlopen(url, timeout=4) as response:
                    xml_data = response.read()
            else:
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
    
    # Gestion des URLs multiples
    urls = data.get('urls', [])
    if isinstance(urls, str):
        urls = [urls]
    urls = [u.strip() for u in urls if u and u.strip()]
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
    
    # Gestion des URLs multiples
    urls = data.get('urls', [])
    if isinstance(urls, str):
        urls = [urls]
    urls = [u.strip() for u in urls if u and u.strip()]
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

@app.route('/api/alerts/resolve-asset/<int:asset_id>', methods=['POST'])
def resolve_asset_alerts(asset_id):
    data = request.get_json(silent=True) or {}
    new_version = data.get('new_version')
    
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
            
    # Récupérer l'ancienne version et le nom du produit
    asset = conn.execute("SELECT nom_produit, version_actuelle FROM assets WHERE id = ?;", (asset_id,)).fetchone()
    ancienne_version = asset['version_actuelle'] if asset else 'N/A'
    nom_produit = asset['nom_produit'] if asset else 'Inconnu'

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
                INSERT INTO update_logs (asset_id, nom_produit, ancienne_version, nouvelle_version, date_maj)
                VALUES (?, ?, ?, ?, ?);
            """, (asset_id, nom_produit, ancienne_version, clean_ver, now_str))
        
    conn.execute("UPDATE alerts SET resolved = 1 WHERE asset_id = ? AND resolved = 0;", (asset_id,))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'updated_version': new_version
    })

@app.route('/api/alerts/refresh', methods=['POST'])
def refresh_alerts():
    conn = get_db_connection()
    assets = conn.execute("SELECT id, nom_produit, version_actuelle FROM assets;").fetchall()
    
    unreachable_urls = []
    new_alerts_count = 0
    
    for asset in assets:
        asset_id = asset['id']
        version_actuelle = asset['version_actuelle']
        
        # Récupérer les URLs configurées pour cet actif
        urls_rows = conn.execute("SELECT url, is_primary FROM asset_urls WHERE asset_id = ? ORDER BY is_primary DESC, id ASC;", (asset_id,)).fetchall()
        
        if not urls_rows:
            continue
            
        triggered_alerts = []
        
        for u_row in urls_rows:
            url = u_row['url']
            is_primary = u_row['is_primary']
            xml_data = None
            
            if url.lower().startswith('opencve://'):
                is_joomla = False
            else:
                try:
                    if url.lower().startswith('file://'):
                        with urllib.request.urlopen(url, timeout=4) as response:
                            xml_data = response.read()
                    else:
                        req = urllib.request.Request(
                            url, 
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) herakles-it-tracker/1.0'}
                        )
                        with urllib.request.urlopen(req, timeout=4) as response:
                            xml_data = response.read()
                except Exception as e:
                    print(f"Erreur de récupération de l'URL ({url}): {e}")
                    unreachable_urls.append(url)
                    continue

                # Détection du format : soit URL se termine par .xml, soit le contenu XML contient updates/update
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
                        continue

                # Extraction de la version
                def find_version_elem(elem):
                    tag = elem.tag.split('}')[-1]
                    if tag == 'version' and elem.text:
                        return elem.text.strip()
                    for child in elem:
                        res = find_version_elem(child)
                        if res:
                            return res
                    return None

                xml_version = find_version_elem(root)
                if not xml_version:
                    continue

                # Comparaison et Alerte
                asset_ver = parse_version_safe(version_actuelle)
                xml_ver = parse_version_safe(xml_version)

                if xml_ver and asset_ver and xml_ver > asset_ver:
                    title = f"Mise à jour disponible : Version {xml_version} disponible (Actuellement en {version_actuelle})"
                    
                    # Extraction de infourl si présent
                    def find_infourl_elem(elem):
                        tag = elem.tag.split('}')[-1]
                        if tag == 'infourl' and elem.text:
                            return elem.text.strip()
                        for child in elem:
                            res = find_infourl_elem(child)
                            if res:
                                return res
                        return None

                    xml_infourl = find_infourl_elem(root)
                    link = xml_infourl if xml_infourl else url
                    pub_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

                    triggered_alert_for_url = {
                        'title': title,
                        'description': f"Une nouvelle version {xml_version} est disponible pour l'actif {asset['nom_produit']}.",
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
                        
                        temp_alert = {
                            'title': title,
                            'description': desc,
                            'version_actuelle': version_actuelle
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

            # Gérer l'insertion, la mise à jour et la résolution des alertes pour cette URL
            active_titles = {a['title'] for a in triggered_alerts}
            
            if not active_titles:
                conn.execute("""
                    UPDATE alerts 
                    SET resolved = 1 
                    WHERE asset_id = ? AND trigger_url = ? AND resolved = 0;
                """, (asset_id, url))
            else:
                placeholders = ', '.join('?' for _ in active_titles)
                query = f"""
                    UPDATE alerts 
                    SET resolved = 1 
                    WHERE asset_id = ? AND trigger_url = ? AND resolved = 0 AND title NOT IN ({placeholders});
                """
                conn.execute(query, [asset_id, url] + list(active_titles))
                
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
                            SELECT id FROM alerts 
                            WHERE asset_id = ? AND trigger_url = ? AND title = ? AND resolved = 1;
                        """, (asset_id, url, a['title'])).fetchone()
                        
                        if existing_resolved:
                            conn.execute("""
                                UPDATE alerts 
                                SET resolved = 0, description = ?, link = ?, pub_date = ?, is_secondary = ?
                                WHERE id = ?;
                            """, (a['description'], a['link'], a['pub_date'], a['is_secondary'], existing_resolved['id']))
                        else:
                            conn.execute("""
                                INSERT INTO alerts (asset_id, title, description, link, pub_date, resolved, trigger_url, is_secondary)
                                VALUES (?, ?, ?, ?, ?, 0, ?, ?);
                            """, (asset_id, a['title'], a['description'], a['link'], a['pub_date'], url, a['is_secondary']))
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

@app.route('/api/update-logs', methods=['GET'])
def get_update_logs():
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM update_logs ORDER BY date_maj DESC, id DESC LIMIT 15;").fetchall()
    conn.close()
    return jsonify([dict(l) for l in logs])

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
        
        # 4. Colonnes alerts
        try:
            conn.execute("ALTER TABLE alerts ADD COLUMN trigger_url TEXT;")
        except sqlite3.OperationalError:
            pass
            
        try:
            conn.execute("ALTER TABLE alerts ADD COLUMN is_secondary INTEGER DEFAULT 0;")
        except sqlite3.OperationalError:
            pass
            
        # 5. Colonne tags pour assets
        try:
            conn.execute("ALTER TABLE assets ADD COLUMN tags TEXT DEFAULT '';")
        except sqlite3.OperationalError:
            pass
            
        conn.commit()
        conn.close()
        print("Mise à jour et migration de la base de données terminées avec succès.")
    except Exception as e:
        print(f"Erreur lors de la mise à jour/migration de la base de données : {e}")
        
    app.run(host='0.0.0.0', port=5000, debug=True)
