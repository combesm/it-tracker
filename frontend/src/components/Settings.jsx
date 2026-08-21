import React, { useState, useEffect } from 'react';
import * as XLSX from 'xlsx';

export default function Settings({ backendUrl }) {
  const [settings, setSettings] = useState({
    teams_webhook_url: '',
    enable_notifications: 'false',
    notification_min_cvss: '7.0',
    refresh_interval_hours: '12',
    last_refresh_time: '',
    cron_token: ''
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState(null); // { type: 'success' | 'error', text: '' }
  const [copied, setCopied] = useState(false);
  const [cronTemplate, setCronTemplate] = useState('office');

  // États pour l'Export et Import Excel
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [filePreview, setFilePreview] = useState(null); // { fileName, team, assets }
  const [importResult, setImportResult] = useState(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${backendUrl}/api/settings`);
      if (res.ok) {
        const data = await res.json();
        setSettings(prev => ({ ...prev, ...data }));
      } else {
        showFeedback('error', 'Impossible de charger les paramètres.');
      }
    } catch (err) {
      console.error(err);
      showFeedback('error', 'Erreur de connexion avec le serveur.');
    } finally {
      setLoading(false);
    }
  };

  const showFeedback = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      const res = await fetch(`${backendUrl}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      if (res.ok) {
        showFeedback('success', 'Paramètres enregistrés avec succès.');
      } else {
        showFeedback('error', 'Échec de la sauvegarde.');
      }
    } catch (err) {
      console.error(err);
      showFeedback('error', 'Erreur de connexion lors de la sauvegarde.');
    } finally {
      setSaving(false);
    }
  };

  const handleTestWebhook = async () => {
    try {
      setTesting(true);
      const res = await fetch(`${backendUrl}/api/settings/test_webhook`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ teams_webhook_url: settings.teams_webhook_url })
      });
      if (res.ok) {
        showFeedback('success', 'Notification de test envoyée avec succès sur Microsoft Teams !');
      } else {
        const data = await res.json();
        showFeedback('error', data.error || 'Erreur lors de l\'envoi du test.');
      }
    } catch (err) {
      console.error(err);
      showFeedback('error', 'Erreur de connexion lors de l\'envoi du test.');
    } finally {
      setTesting(false);
    }
  };

  // Handler pour l'export Excel
  const handleExportExcel = async () => {
    try {
      setExporting(true);
      // 1. Récupération des Actifs
      const resAssets = await fetch(`${backendUrl}/api/assets`);
      const assets = resAssets.ok ? await resAssets.json() : [];

      // 2. Récupération de l'Équipe
      const resTeam = await fetch(`${backendUrl}/api/team`);
      const team = resTeam.ok ? await resTeam.json() : [];

      // 3. Récupération des Logs et des Alertes Résolues
      const [resLogs, resAlerts] = await Promise.all([
        fetch(`${backendUrl}/api/update-logs`),
        fetch(`${backendUrl}/api/alerts/resolved`)
      ]);

      const logsDataRaw = resLogs.ok ? await resLogs.json() : [];
      const alertsDataRaw = resAlerts.ok ? await resAlerts.json() : [];

      const formatDateStr = (dateStr) => {
        if (!dateStr) return 'N/A';
        if (typeof dateStr === 'string' && /^\d{2}\/\d{2}\/\d{4}\s+\d{2}:\d{2}/.test(dateStr)) {
          return dateStr;
        }
        try {
          const d = new Date(dateStr);
          if (isNaN(d.getTime())) return dateStr;
          const pad = (n) => String(n).padStart(2, '0');
          const day = pad(d.getDate());
          const month = pad(d.getMonth() + 1);
          const year = d.getFullYear();
          const hours = pad(d.getHours());
          const minutes = pad(d.getMinutes());
          return `${day}/${month}/${year} ${hours}:${minutes}`;
        } catch {
          return dateStr;
        }
      };

      const parseTs = (dateStr) => {
        if (!dateStr) return 0;
        const frMatch = String(dateStr).match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2}))?/);
        if (frMatch) {
          const [, day, month, year, hours = '00', minutes = '00'] = frMatch;
          return new Date(year, month - 1, day, hours, minutes).getTime();
        }
        const parsed = Date.parse(dateStr);
        return isNaN(parsed) ? 0 : parsed;
      };

      const isSecurityAlert = (alert) => {
        const title = (alert.title || '').toLowerCase();
        const desc = (alert.description || '').toLowerCase();
        const full = `${title} ${desc}`;
        if (title.startsWith('mise à jour disponible')) return false;
        const securityKeywords = ['cve-', 'certfr-', 'cvss', 'vulnérabilité', 'vulnerabilite', 'faille', 'sécurité', 'securite', 'exploit', 'advisory', 'patch de sécurité'];
        return securityKeywords.some(kw => full.includes(kw));
      };

      // Mises à jour
      const formattedUpdateLogs = logsDataRaw.map(l => ({
        "Type d'événement": "MAJ",
        "Date & Heure": l.date_maj || 'N/A',
        "Actif": l.nom_produit || '',
        "Détails de l'événement": `Passage de ${l.ancienne_version || 'N/A'} à ${l.nouvelle_version || ''}`,
        "Résolveur": l.resolved_by || 'N/A',
        sortTime: parseTs(l.date_maj)
      }));

      // Alertes / CVEs résolues
      const formattedCveLogs = alertsDataRaw
        .filter(a => isSecurityAlert(a))
        .map(a => {
          const dateVal = a.resolved_at || a.pub_date;
          return {
            "Type d'événement": "CVE",
            "Date & Heure": formatDateStr(dateVal),
            "Actif": a.nom_produit || '',
            "Détails de l'événement": `${a.title || ''} (Résolu en v${a.resolved_at_version || 'N/A'})`,
            "Résolveur": a.resolved_by || a.responsable || 'N/A',
            sortTime: parseTs(dateVal)
          };
        });

      // Combiner et trier chronologiquement
      const allLogsFormatted = [...formattedUpdateLogs, ...formattedCveLogs];
      allLogsFormatted.sort((a, b) => (b.sortTime || 0) - (a.sortTime || 0));

      const cleanLogsExport = allLogsFormatted.map(({ sortTime, ...rest }) => rest);

      // Initialiser le classeur Excel
      const wb = XLSX.utils.book_new();

      // Onglet 1 : Actifs & Services (avec étiquettes et sources RSS/Vigil)
      const assetsData = assets.map(a => ({
        "Nom du produit": a.nom_produit || '',
        "Entités": a.entites || 'Groupe',
        "Fournisseur": a.fournisseur || '',
        "Version actuelle": a.version_actuelle || '',
        "Type de déploiement": a.type_deploiement || '',
        "Hébergement / Machine": a.machine_hebergement || '',
        "Type de licence": a.type_licence || 'Perpétuelle',
        "Date d'expiration": a.date_expiration ? a.date_expiration : '',
        "Responsable (Trigramme)": a.responsable || '',
        "Email Responsable": a.email_responsable || '',
        "Sources RSS / Vigil": (a.urls && a.urls.length > 0) ? a.urls.join(', ') : (a.url_rss || ''),
        "Étiquettes": Array.isArray(a.tags) ? a.tags.join(', ') : (a.tags || '')
      }));
      const wsAssets = XLSX.utils.json_to_sheet(assetsData);
      XLSX.utils.book_append_sheet(wb, wsAssets, "Actifs & Services");

      // Onglet 2 : Membres de l'Équipe
      const teamData = team.map(t => ({
        "Trigramme": t.trigramme || '',
        "Adresse Email": t.email || ''
      }));
      const wsTeam = XLSX.utils.json_to_sheet(teamData);
      XLSX.utils.book_append_sheet(wb, wsTeam, "Membres de l'Équipe");

      // Onglet 3 : Logs & Historique
      const wsLogs = XLSX.utils.json_to_sheet(cleanLogsExport);
      XLSX.utils.book_append_sheet(wb, wsLogs, "Logs & Historique");

      // Télécharger le fichier Excel
      XLSX.writeFile(wb, "Inventaire_IT_Herakles.xlsx");
      showFeedback('success', 'Inventaire Excel et Historique des Logs exportés avec succès !');
    } catch (err) {
      console.error("Erreur lors de l'export Excel:", err);
      showFeedback('error', "Une erreur est survenue lors de la génération du fichier Excel.");
    } finally {
      setExporting(false);
    }
  };

  // Handler de lecture et parsing du fichier Excel lors de la sélection
  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const data = new Uint8Array(evt.target.result);
        const workbook = XLSX.read(data, { type: 'array' });

        let teamSheetName = workbook.SheetNames.find(n =>
          n.toLowerCase().includes('équipe') ||
          n.toLowerCase().includes('equipe') ||
          n.toLowerCase().includes('team') ||
          n.toLowerCase().includes('membre')
        );
        let assetsSheetName = workbook.SheetNames.find(n =>
          n.toLowerCase().includes('actif') ||
          n.toLowerCase().includes('asset') ||
          n.toLowerCase().includes('service')
        );

        if (!assetsSheetName && workbook.SheetNames.length > 0) assetsSheetName = workbook.SheetNames[0];
        if (!teamSheetName && workbook.SheetNames.length > 1) teamSheetName = workbook.SheetNames[1];

        let rawAssets = assetsSheetName ? XLSX.utils.sheet_to_json(workbook.Sheets[assetsSheetName], { defval: '' }) : [];
        let rawTeam = (teamSheetName && teamSheetName !== assetsSheetName) ? XLSX.utils.sheet_to_json(workbook.Sheets[teamSheetName], { defval: '' }) : [];

        const getKey = (row, candidates) => {
          const rowKeys = Object.keys(row);
          for (const cand of candidates) {
            const match = rowKeys.find(k => k.trim().toLowerCase() === cand.toLowerCase());
            if (match !== undefined) return row[match];
          }
          return '';
        };

        const parsedTeam = rawTeam.map(row => ({
          trigramme: String(getKey(row, ['Trigramme', 'Trig', 'Trigramme (3 lettres)'])).trim().toUpperCase(),
          email: String(getKey(row, ['Adresse Email', 'Email', 'E-mail', 'Mail', 'Courriel'])).trim()
        })).filter(t => t.trigramme || t.email);

        const parsedAssets = rawAssets.map(row => ({
          nom_produit: String(getKey(row, ['Nom du produit', 'Produit', 'Nom'])).trim(),
          entites: String(getKey(row, ['Entités', 'Entites', 'Entité', 'Entite'])).trim() || 'Groupe',
          fournisseur: String(getKey(row, ['Fournisseur'])).trim(),
          version_actuelle: String(getKey(row, ['Version actuelle', 'Version'])).trim(),
          type_deploiement: String(getKey(row, ['Type de déploiement', 'Type de deploiement', 'Déploiement', 'Deploiement'])).trim(),
          machine_hebergement: String(getKey(row, ['Hébergement / Machine', 'Hebergement / Machine', 'Machine', 'Hébergement', 'Hebergement'])).trim(),
          type_licence: String(getKey(row, ['Type de licence', 'Licence'])).trim() || 'Perpétuelle',
          date_expiration: String(getKey(row, ['Date d\'expiration', 'Date expiration', 'Expiration'])).trim(),
          responsable: String(getKey(row, ['Responsable (Trigramme)', 'Responsable', 'Trigramme'])).trim().toUpperCase(),
          urls: String(getKey(row, ['Sources RSS / Vigil', 'Flux RSS', 'URL RSS', 'RSS', 'Sources', 'URLs', 'URL'])).trim(),
          tags: String(getKey(row, ['Étiquettes', 'Etiquettes', 'Tags', 'Tag'])).trim()
        })).filter(a => a.nom_produit || a.version_actuelle || a.responsable);

        setFilePreview({
          fileName: file.name,
          team: parsedTeam,
          assets: parsedAssets
        });
        setImportResult(null);
      } catch (err) {
        console.error("Erreur de lecture Excel:", err);
        showFeedback('error', "Impossible de lire le fichier Excel. Format non valide.");
      }
    };
    reader.readAsArrayBuffer(file);
    e.target.value = '';
  };

  // Handler de confirmation de l'import
  const handleExecuteImport = async () => {
    if (!filePreview) return;
    try {
      setImporting(true);
      const res = await fetch(`${backendUrl}/api/import/excel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          team: filePreview.team,
          assets: filePreview.assets
        })
      });

      if (res.ok) {
        const result = await res.json();
        setImportResult(result);
        setFilePreview(null);
        showFeedback('success', 'Importation Excel réalisée avec succès !');
      } else {
        const errData = await res.json();
        showFeedback('error', errData.error || 'Erreur lors de l\'importation.');
      }
    } catch (err) {
      console.error(err);
      showFeedback('error', 'Erreur de connexion lors de l\'importation.');
    } finally {
      setImporting(false);
    }
  };

  const absoluteCronUrl = `${window.location.protocol}//${window.location.host}${backendUrl}/api/alerts/cron_check?token=${settings.cron_token}`;

  let cronSchedule = '*/30 * * * *';
  if (settings.refresh_interval_hours === '0') {
    if (cronTemplate === 'office') {
      cronSchedule = '0 9,12,15 * * 1-5';
    } else if (cronTemplate === 'daily') {
      cronSchedule = '0 10 * * *';
    } else if (cronTemplate === 'weekly') {
      cronSchedule = '0 8 * * 1';
    }
  }
  const cronCmd = `${cronSchedule} curl -s -X POST "${absoluteCronUrl}" > /dev/null`;

  const handleCopyCron = () => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(cronCmd)
        .then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        })
        .catch(err => {
          console.error('Failed to copy using navigator.clipboard: ', err);
          fallbackCopyTextToClipboard(cronCmd);
        });
    } else {
      fallbackCopyTextToClipboard(cronCmd);
    }
  };

  const fallbackCopyTextToClipboard = (text) => {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.top = "-9999px";
    textArea.style.left = "-9999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      const successful = document.execCommand('copy');
      if (successful) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } else {
        console.error('Fallback: Copying text command was unsuccessful');
      }
    } catch (err) {
      console.error('Fallback: Unable to copy', err);
    }
    document.body.removeChild(textArea);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <svg className="animate-spin h-8 w-8 text-brand-primary" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-brand-dark">Paramètres</h1>
        <p className="text-sm text-brand-text/70 mt-1">
          Configurez les notifications automatiques, l'importation/exportation de vos données et la planification des vérifications.
        </p>
      </div>

      {message && (
        <div className={`p-4 rounded-lg text-sm font-semibold flex items-center transition-all ${message.type === 'success' ? 'bg-brand-successBg text-brand-success' : 'bg-red-50 text-red-700 border border-red-200'
          }`}>
          {message.type === 'success' ? (
            <svg className="w-5 h-5 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
          ) : (
            <svg className="w-5 h-5 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
            </svg>
          )}
          {message.text}
        </div>
      )}

      {/* Section Gestion des Données : Import & Export Excel */}
      <div className="bg-brand-card p-6 rounded-2xl border border-brand-border shadow-sm space-y-6">
        <h2 className="text-lg font-bold text-brand-dark flex items-center border-b border-brand-border pb-3">
          <svg className="w-5 h-5 mr-2 text-[#338D35]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
          </svg>
          Gestion des Données (Import & Export Excel)
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Sous-carte Export */}
          <div className="p-5 rounded-xl bg-brand-bg/30 border border-brand-border space-y-3 flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-bold text-brand-dark flex items-center">
                <svg className="w-4 h-4 mr-2 text-[#338D35]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                </svg>
                Exporter l'inventaire
              </h3>
              <p className="text-xs text-brand-text/70 mt-1">
                Téléchargez la totalité de vos actifs, la liste des membres d'équipe ainsi que le journal complet des logs et de l'historique au format Excel (`.xlsx`).
              </p>
            </div>

            <button
              type="button"
              onClick={handleExportExcel}
              disabled={exporting}
              className="w-full mt-4 px-4 py-2.5 text-xs font-semibold rounded-lg text-white transition-all shadow-sm flex items-center justify-center cursor-pointer disabled:opacity-50"
              style={{ backgroundColor: '#338D35' }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = '#2a7329'}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = '#338D35'}
            >
              {exporting ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Génération en cours...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                  </svg>
                  Exporter en Excel
                </>
              )}
            </button>
          </div>

          {/* Sous-carte Import */}
          <div className="p-5 rounded-xl bg-brand-bg/30 border border-brand-border space-y-3 flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-bold text-brand-dark flex items-center">
                <svg className="w-4 h-4 mr-2 text-brand-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
                </svg>
                Importer depuis un fichier Excel
              </h3>
              <p className="text-xs text-brand-text/70 mt-1">
                Importez de nouveaux actifs et membres d'équipe (ou mettez à jour les existants) à partir d'un fichier `.xlsx`.
              </p>
            </div>

            <div className="mt-4">
              <label className="w-full flex flex-col items-center px-4 py-3 bg-white border border-brand-border rounded-lg shadow-sm cursor-pointer hover:border-brand-primary transition-all text-center">
                <svg className="w-5 h-5 text-brand-primary mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                </svg>
                <span className="text-xs font-semibold text-brand-dark">Choisir un fichier Excel</span>
                <span className="text-[10px] text-brand-text/50">.xlsx, .xls</span>
                <input
                  type="file"
                  accept=".xlsx, .xls"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </label>
            </div>
          </div>
        </div>

        {/* Aperçu du fichier avant import */}
        {filePreview && (
          <div className="p-4 rounded-xl bg-brand-primary/5 border border-brand-primary/20 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <svg className="w-5 h-5 text-brand-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
                <span className="text-xs font-bold text-brand-dark">Fichier sélectionné : {filePreview.fileName}</span>
              </div>
              <button
                type="button"
                onClick={() => setFilePreview(null)}
                className="text-xs text-red-500 hover:text-red-700 font-semibold cursor-pointer"
              >
                Annuler
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs text-brand-dark">
              <div className="bg-white p-3 rounded-lg border border-brand-border">
                <span className="font-semibold block text-brand-primary">Membres d'équipe détectés :</span>
                <span className="text-base font-bold">{filePreview.team.length}</span>
              </div>
              <div className="bg-white p-3 rounded-lg border border-brand-border">
                <span className="font-semibold block text-brand-primary">Actifs & Services détectés :</span>
                <span className="text-base font-bold">{filePreview.assets.length}</span>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={handleExecuteImport}
                disabled={importing || (filePreview.team.length === 0 && filePreview.assets.length === 0)}
                className="px-5 py-2 text-xs font-semibold rounded-lg bg-brand-primary text-white hover:bg-brand-primary/95 transition-all flex items-center cursor-pointer disabled:opacity-50"
              >
                {importing ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Importation en cours...
                  </>
                ) : (
                  'Lancer l\'importation'
                )}
              </button>
            </div>
          </div>
        )}

        {/* Compte-rendu de l'import */}
        {importResult && (
          <div className="p-4 rounded-xl bg-brand-successBg/40 border border-brand-success/30 space-y-3">
            <div className="flex items-center space-x-2 text-brand-success font-bold text-xs">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
              </svg>
              <span>Rapport d'importation terminé</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-brand-dark">
              <div className="bg-white p-2.5 rounded-lg border border-brand-border">
                <span className="text-[10px] text-brand-text/70 block">Membres créés</span>
                <span className="font-bold text-brand-success">{importResult.team_added}</span>
              </div>
              <div className="bg-white p-2.5 rounded-lg border border-brand-border">
                <span className="text-[10px] text-brand-text/70 block">Membres mis à jour</span>
                <span className="font-bold text-blue-600">{importResult.team_updated}</span>
              </div>
              <div className="bg-white p-2.5 rounded-lg border border-brand-border">
                <span className="text-[10px] text-brand-text/70 block">Actifs créés</span>
                <span className="font-bold text-brand-success">{importResult.assets_added}</span>
              </div>
              <div className="bg-white p-2.5 rounded-lg border border-brand-border">
                <span className="text-[10px] text-brand-text/70 block">Actifs mis à jour</span>
                <span className="font-bold text-blue-600">{importResult.assets_updated}</span>
              </div>
            </div>

            {importResult.errors && importResult.errors.length > 0 && (
              <div className="mt-3 p-3 bg-red-50 rounded-lg border border-red-200 text-xs space-y-1">
                <span className="font-bold text-red-700 block">Avertissements / Erreurs ({importResult.errors.length}) :</span>
                <ul className="list-disc list-inside text-red-600 space-y-0.5 max-h-32 overflow-y-auto">
                  {importResult.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Paramètres Form Card */}
        <div className="lg:col-span-2 bg-brand-card p-6 rounded-2xl border border-brand-border shadow-sm space-y-6">
          <h2 className="text-lg font-bold text-brand-dark flex items-center border-b border-brand-border pb-3">
            <svg className="w-5 h-5 mr-2 text-brand-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path>
            </svg>
            Notifications Microsoft Teams
          </h2>

          <form onSubmit={handleSave} className="space-y-6">
            {/* Activer/Désactiver */}
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="enable_notifications"
                checked={settings.enable_notifications === 'true'}
                onChange={(e) => setSettings({ ...settings, enable_notifications: e.target.checked ? 'true' : 'false' })}
                className="h-5 w-5 rounded border-brand-border text-brand-primary focus:ring-brand-primary cursor-pointer animate-none"
              />
              <label htmlFor="enable_notifications" className="text-sm font-semibold text-brand-dark cursor-pointer select-none">
                Activer les notifications automatiques d'alertes de sécurité
              </label>
            </div>

            {/* URL Webhook */}
            <div className="space-y-2">
              <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider">
                URL du Webhook Teams
              </label>
              <input
                type="url"
                placeholder="https://outlook.office.com/webhook/..."
                value={settings.teams_webhook_url}
                onChange={(e) => setSettings({ ...settings, teams_webhook_url: e.target.value })}
                className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary bg-brand-bg/20"
                disabled={settings.enable_notifications !== 'true'}
              />
            </div>

            {/* Filtre score CVSS & Fréquence */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Score CVSS Minimum */}
              <div className="space-y-2">
                <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider">
                  Score CVSS Minimum pour Notification : <span className="text-brand-primary font-bold">{settings.notification_min_cvss}</span>
                </label>
                <div className="flex items-center space-x-4">
                  <input
                    type="range"
                    min="0"
                    max="10"
                    step="0.5"
                    value={settings.notification_min_cvss}
                    onChange={(e) => setSettings({ ...settings, notification_min_cvss: e.target.value })}
                    className="w-full h-2 bg-brand-border rounded-lg appearance-none cursor-pointer accent-brand-primary"
                    disabled={settings.enable_notifications !== 'true'}
                  />
                  <span className="text-sm font-semibold text-brand-dark bg-brand-bg px-2.5 py-1 rounded-md border border-brand-border">
                    {settings.notification_min_cvss}
                  </span>
                </div>
              </div>

              {/* Fréquence de rafraîchissement */}
              <div className="space-y-2">
                <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider">
                  Fréquence de synchronisation
                </label>
                <select
                  value={settings.refresh_interval_hours}
                  onChange={(e) => setSettings({ ...settings, refresh_interval_hours: e.target.value })}
                  className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary bg-brand-bg/20 cursor-pointer"
                  disabled={settings.enable_notifications !== 'true'}
                >
                  <option value="0">Géré par le Cron externe (À chaque appel)</option>
                  <option value="1">Toutes les 1 heure</option>
                  <option value="3">Toutes les 3 heures</option>
                  <option value="6">Toutes les 6 heures</option>
                  <option value="12">Toutes les 12 heures</option>
                  <option value="24">Toutes les 24 heures</option>
                </select>
              </div>
            </div>

            {/* Actions de validation */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-4 border-t border-brand-border">
              <button
                type="button"
                onClick={handleTestWebhook}
                disabled={testing || !settings.teams_webhook_url}
                className="px-4 py-2 text-xs font-semibold rounded-lg border border-brand-primary/50 text-brand-primary hover:bg-brand-primary/5 transition-all flex items-center justify-center cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {testing ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-brand-primary" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Envoi du test...
                  </>
                ) : (
                  'Envoyer une notification de test'
                )}
              </button>

              <button
                type="submit"
                disabled={saving}
                className="px-6 py-2 text-xs font-semibold rounded-lg bg-brand-primary text-white hover:bg-brand-primary/95 transition-all flex items-center justify-center shadow-sm cursor-pointer disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Enregistrement...
                  </>
                ) : (
                  'Enregistrer les modifications'
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Aide Cron Integration Card */}
        <div className="bg-brand-card p-6 rounded-2xl border border-brand-border shadow-sm space-y-6">
          <h2 className="text-lg font-bold text-brand-dark flex items-center border-b border-brand-border pb-3">
            <svg className="w-5 h-5 mr-2 text-brand-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            Planification (Cron)
          </h2>

          <div className="space-y-4 text-sm text-brand-text/80">
            <p>
              Pour rendre la détection d'alertes autonome, configurez une tâche Cron sur votre serveur hôte.
            </p>
            <p>
              {settings.refresh_interval_hours === '0' ? (
                "L'application exécutera la synchronisation à chaque fois que la tâche Cron l'appellera. Vous déterminez la planification exacte directement dans la tâche Cron ci-dessous."
              ) : (
                `La tâche Cron appellera l'application à intervalle régulier. Le système vérifiera automatiquement le temps écoulé et n'exécutera le rafraîchissement que si ${settings.refresh_interval_hours}h se sont écoulées.`
              )}
            </p>

            {settings.refresh_interval_hours === '0' && (
              <div className="space-y-2">
                <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider">
                  Modèle de planification Cron
                </label>
                <select
                  value={cronTemplate}
                  onChange={(e) => setCronTemplate(e.target.value)}
                  className="w-full px-3 py-1.5 text-xs border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary bg-brand-bg/20 cursor-pointer"
                >
                  <option value="office">Heures de bureau (9h, 12h, 15h - Lun-Ven)</option>
                  <option value="daily">Quotidien (Tous les jours à 10h)</option>
                  <option value="weekly">Hebdomadaire (Chaque lundi à 8h)</option>
                </select>
              </div>
            )}

            <div className="space-y-2 pt-2">
              <span className="block text-xs font-bold text-brand-dark uppercase tracking-wider">
                Commande Cron Recommandée
              </span>
              <div className="relative group">
                <pre className="bg-brand-bg p-3 rounded-lg text-xs font-mono break-all text-brand-dark border border-brand-border select-all pr-12 whitespace-pre-wrap">
                  {cronCmd}
                </pre>
                <button
                  type="button"
                  onClick={handleCopyCron}
                  title="Copier la commande"
                  className="absolute right-2 top-2 p-1.5 rounded-md hover:bg-brand-border text-brand-primary transition-all cursor-pointer"
                >
                  {copied ? (
                    <svg className="w-4 h-4 text-brand-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"></path>
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {settings.last_refresh_time && (
              <div className="pt-4 border-t border-brand-border text-xs text-brand-text/60">
                Dernière synchronisation automatique :
                <span className="block font-semibold text-brand-dark mt-1">
                  {new Date(settings.last_refresh_time).toLocaleString('fr-FR')}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
