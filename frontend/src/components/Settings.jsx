import React, { useState, useEffect } from 'react';

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
          Configurez les notifications automatiques d'alertes de sécurité et la planification des vérifications.
        </p>
      </div>

      {message && (
        <div className={`p-4 rounded-lg text-sm font-semibold flex items-center transition-all ${
          message.type === 'success' ? 'bg-brand-successBg text-brand-success' : 'bg-red-50 text-red-700 border border-red-200'
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
              Pour rendre la détection d'alertes autonome, configurez une tâche **Cron** sur votre serveur hôte.
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
