import React, { useState, useEffect } from 'react';

export default function Dashboard({ backendUrl }) {
  const [stats, setStats] = useState({ total_assets: 0, expiring_licences: 0, pending_alerts: 0 });
  const [alerts, setAlerts] = useState([]);
  const [certAlerts, setCertAlerts] = useState([]);
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [loadingCert, setLoadingCert] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [certErrorMessage, setCertErrorMessage] = useState('');
  const [unreachableFeeds, setUnreachableFeeds] = useState([]);
  const [successMessage, setSuccessMessage] = useState('');
  const [expandedAssetId, setExpandedAssetId] = useState(null);

  // States for Resolution Modal
  const [resolutionModalOpen, setResolutionModalOpen] = useState(false);
  const [selectedAssetForResolution, setSelectedAssetForResolution] = useState(null);
  const [resolutionNewVersion, setResolutionNewVersion] = useState('');

  // States for Update Logs
  const [updateLogs, setUpdateLogs] = useState([]);
  const [loadingLogs, setLoadingLogs] = useState(true);

  const fetchStats = async () => {
    try {
      setLoadingStats(true);
      const res = await fetch(`${backendUrl}/api/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error("Erreur lors de la récupération des statistiques:", err);
    } finally {
      setLoadingStats(false);
    }
  };

  const fetchAlerts = async () => {
    try {
      setLoadingAlerts(true);
      const res = await fetch(`${backendUrl}/api/alerts`);
      if (res.ok) {
        const data = await res.json();
        setAlerts(data);
      }
    } catch (err) {
      console.error("Erreur lors de la récupération des alertes:", err);
    } finally {
      setLoadingAlerts(false);
    }
  };

  const fetchCertAlerts = async () => {
    try {
      setLoadingCert(true);
      setCertErrorMessage('');
      const res = await fetch(`${backendUrl}/api/cert-rss`);
      if (res.ok) {
        const data = await res.json();
        setCertAlerts(data.items || []);
      } else {
        const errorData = await res.json();
        setCertErrorMessage(errorData.error || 'Le flux CERT-FR est temporairement injoignable.');
      }
    } catch (err) {
      setCertErrorMessage('Impossible de contacter le serveur pour charger le flux CERT-FR.');
      console.error("Erreur lors de la récupération du flux CERT-FR:", err);
    } finally {
      setLoadingCert(false);
    }
  };

  const fetchUpdateLogs = async () => {
    try {
      setLoadingLogs(true);
      const res = await fetch(`${backendUrl}/api/update-logs`);
      if (res.ok) {
        const data = await res.json();
        setUpdateLogs(data);
      }
    } catch (err) {
      console.error("Erreur lors du chargement de l'historique:", err);
    } finally {
      setLoadingLogs(false);
    }
  };

  const handleRefreshAlerts = async () => {
    try {
      setRefreshing(true);
      setErrorMessage('');
      setSuccessMessage('');
      setUnreachableFeeds([]);
      
      const res = await fetch(`${backendUrl}/api/alerts/refresh`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setAlerts(data.alerts);
        
        if (data.unreachable_urls && data.unreachable_urls.length > 0) {
          setUnreachableFeeds(data.unreachable_urls);
        }
        
        const count = data.new_alerts_count;
        if (count > 0) {
          setSuccessMessage(`${count} nouvelle(s) alerte(s) récupérée(s) avec succès.`);
        } else {
          setSuccessMessage('Mise à jour terminée. Aucune nouvelle alerte détectée.');
        }
        
        // Rafraîchir aussi les stats
        fetchStats();
      } else {
        setErrorMessage('Une erreur est survenue lors de la synchronisation des flux.');
      }
    } catch (err) {
      setErrorMessage('Erreur réseau lors de la synchronisation.');
      console.error(err);
    } finally {
      setRefreshing(false);
    }
  };

  const handleResolveAssetAlerts = async (assetId, newVersion) => {
    try {
      const res = await fetch(`${backendUrl}/api/alerts/resolve-asset/${assetId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_version: newVersion })
      });
      if (res.ok) {
        // Retirer toutes les alertes de cet actif de l'état local
        setAlerts(prev => prev.filter(a => a.asset_id !== assetId));
        // Rafraîchir les stats
        fetchStats();
        // Rafraîchir le journal d'historique
        fetchUpdateLogs();
      } else {
        alert('Erreur lors de la validation des alertes de l\'actif.');
      }
    } catch (err) {
      console.error("Erreur de réseau lors de la validation de l'actif:", err);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchAlerts();
    fetchCertAlerts();
    fetchUpdateLogs();
  }, []);

  // Formater la date en français propre
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateStr;
    }
  };

  // Groupement des alertes par actif pour affichage pliable
  const getGroupedAlerts = () => {
    const grouped = {};
    alerts.forEach(alert => {
      const assetId = alert.asset_id;
      if (!grouped[assetId]) {
        grouped[assetId] = {
          asset_id: assetId,
          nom_produit: alert.nom_produit,
          responsable: alert.responsable,
          alerts: [],
          latest_pub_date: alert.pub_date || '',
          version_actuelle: alert.version_actuelle
        };
      }
      grouped[assetId].alerts.push(alert);
      
      if (alert.pub_date) {
        if (!grouped[assetId].latest_pub_date) {
          grouped[assetId].latest_pub_date = alert.pub_date;
        } else {
          const currentLatest = new Date(grouped[assetId].latest_pub_date);
          const itemDate = new Date(alert.pub_date);
          if (itemDate > currentLatest) {
            grouped[assetId].latest_pub_date = alert.pub_date;
          }
        }
      }
    });
    
    const list = Object.values(grouped);
    list.sort((a, b) => {
      if (!a.latest_pub_date) return 1;
      if (!b.latest_pub_date) return -1;
      return new Date(b.latest_pub_date) - new Date(a.latest_pub_date);
    });
    return list;
  };

  const groupedAlertList = getGroupedAlerts();

  const toggleExpand = (assetId) => {
    setExpandedAssetId(prev => prev === assetId ? null : assetId);
  };

  return (
    <div className="space-y-8">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold text-brand-dark">Tableau de bord</h1>
        <p className="text-sm text-brand-text/70 mt-1">
          Aperçu global de l'infrastructure, gestion des licences et vulnérabilités détectées.
        </p>
      </div>

      {/* KPI Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* KPI 1 : Actifs */}
        <div className="bg-brand-card rounded-lg border border-brand-border p-6 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-brand-text/60 uppercase tracking-wider">Actifs & Services</span>
            {loadingStats ? (
              <div className="h-9 w-16 bg-brand-bg animate-pulse rounded mt-2"></div>
            ) : (
              <h2 className="text-3xl font-bold text-brand-dark mt-1">{stats.total_assets}</h2>
            )}
          </div>
          <div className="p-3 bg-brand-bg rounded-lg text-brand-dark">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
            </svg>
          </div>
        </div>

        {/* KPI 2 : Licences expirant bientôt */}
        <div className={`bg-brand-card rounded-lg border p-6 shadow-sm flex items-center justify-between transition-colors duration-200 ${
          stats.expiring_licences > 0 ? 'border-brand-alert/40 bg-brand-alertBg/30' : 'border-brand-border'
        }`}>
          <div>
            <span className="text-sm font-medium text-brand-text/60 uppercase tracking-wider">Licences expirant soon (&lt; 30j)</span>
            {loadingStats ? (
              <div className="h-9 w-16 bg-brand-bg animate-pulse rounded mt-2"></div>
            ) : (
              <h2 className={`text-3xl font-bold mt-1 ${stats.expiring_licences > 0 ? 'text-brand-alert' : 'text-brand-dark'}`}>
                {stats.expiring_licences}
              </h2>
            )}
          </div>
          <div className={`p-3 rounded-lg ${stats.expiring_licences > 0 ? 'bg-brand-alert/10 text-brand-alert' : 'bg-brand-bg text-brand-dark'}`}>
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
            </svg>
          </div>
        </div>

        {/* KPI 3 : Alertes en attente */}
        <div className={`bg-brand-card rounded-lg border p-6 shadow-sm flex items-center justify-between transition-colors duration-200 ${
          stats.pending_alerts > 0 ? 'border-brand-alert/40 bg-brand-alertBg/30' : 'border-brand-border'
        }`}>
          <div>
            <span className="text-sm font-medium text-brand-text/60 uppercase tracking-wider">Alertes en attente</span>
            {loadingStats ? (
              <div className="h-9 w-16 bg-brand-bg animate-pulse rounded mt-2"></div>
            ) : (
              <h2 className={`text-3xl font-bold mt-1 ${stats.pending_alerts > 0 ? 'text-brand-alert' : 'text-brand-dark'}`}>
                {stats.pending_alerts}
              </h2>
            )}
          </div>
          <div className={`p-3 rounded-lg ${stats.pending_alerts > 0 ? 'bg-brand-alert/10 text-brand-alert' : 'bg-brand-bg text-brand-dark'}`}>
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path>
            </svg>
          </div>
        </div>
      </div>

      {/* Main Panel: Priority Actions */}
      <div className="bg-brand-card rounded-lg border border-brand-border shadow-sm">
        {/* Card Header */}
        <div className="px-6 py-5 border-b border-brand-border flex items-center justify-between bg-white">
          <div>
            <h3 className="text-lg font-bold text-brand-dark">Actions prioritaires (Alertes RSS)</h3>
            <p className="text-xs text-brand-text/60 mt-0.5">
              Vulnérabilités et correctifs identifiés via les flux RSS configurés sur vos actifs (groupés par actif).
            </p>
          </div>
          <button
            onClick={handleRefreshAlerts}
            disabled={refreshing}
            className={`px-4 py-2 text-xs font-semibold rounded-lg bg-brand-primary text-white hover:bg-brand-primary/95 transition-all flex items-center shadow-sm ${
              refreshing ? 'opacity-70 cursor-not-allowed' : ''
            }`}
          >
            {refreshing ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Mise à jour...
              </>
            ) : (
              'Synchroniser les flux'
            )}
          </button>
        </div>

        {/* Success/Error Alerts */}
        <div className="px-6 pt-4 space-y-2">
          {successMessage && (
            <div className="p-3 bg-brand-successBg text-brand-success rounded-lg text-xs font-medium border border-brand-success/20">
              {successMessage}
            </div>
          )}

          {errorMessage && (
            <div className="p-3 bg-brand-alertBg text-brand-alert rounded-lg text-xs font-medium border border-brand-alert/20">
              {errorMessage}
            </div>
          )}

          {unreachableFeeds.length > 0 && (
            <div className="p-3 bg-brand-alertBg text-brand-alert rounded-lg text-xs font-medium border border-brand-alert/20">
              <span className="font-semibold block mb-1">Certains flux RSS n'ont pas pu être contactés :</span>
              <ul className="list-disc pl-4 space-y-0.5">
                {unreachableFeeds.map((url, idx) => (
                  <li key={idx} className="break-all">{url}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Card Body Table */}
        <div className="p-6">
          {loadingAlerts ? (
            <div className="space-y-4 py-4">
              <div className="h-6 bg-brand-bg animate-pulse rounded w-3/4"></div>
              <div className="h-6 bg-brand-bg animate-pulse rounded w-2/3"></div>
              <div className="h-6 bg-brand-bg animate-pulse rounded w-1/2"></div>
            </div>
          ) : groupedAlertList.length === 0 ? (
            <div className="text-center py-12 bg-brand-bg/30 rounded-lg border border-dashed border-brand-border">
              <span className="text-sm text-brand-text/50 font-medium">
                Aucune alerte en attente. Votre infrastructure est saine et à jour.
              </span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-brand-border animate-none">
                <thead>
                  <tr className="bg-brand-bg/50">
                    <th scope="col" className="w-12 px-4 py-3 text-center text-xs font-bold text-brand-dark uppercase tracking-wider"></th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Actif</th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Sécurité (CVE)</th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Mises à jour</th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Dernière publication</th>
                    <th scope="col" className="px-4 py-3 text-center text-xs font-bold text-brand-dark uppercase tracking-wider">Responsable</th>
                    <th scope="col" className="px-4 py-3 text-right text-xs font-bold text-brand-dark uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-brand-border">
                  {groupedAlertList.map((asset) => {
                    const isExpanded = expandedAssetId === asset.asset_id;
                    return (
                      <React.Fragment key={asset.asset_id}>
                        {/* Group Row */}
                        <tr 
                          onClick={() => toggleExpand(asset.asset_id)}
                          className={`hover:bg-brand-bg/20 cursor-pointer transition-colors ${
                            isExpanded ? 'bg-brand-bg/10' : ''
                          }`}
                        >
                          {/* Chevron */}
                          <td className="px-4 py-4 text-center">
                            <div className="flex items-center justify-center">
                              <svg 
                                className={`w-4 h-4 text-brand-text/50 transition-transform duration-200 ${
                                  isExpanded ? 'rotate-90' : ''
                                }`} 
                                fill="none" 
                                stroke="currentColor" 
                                viewBox="0 0 24 24" 
                                xmlns="http://www.w3.org/2000/svg"
                              >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 5l7 7-7 7"></path>
                              </svg>
                            </div>
                          </td>
                          {/* Actif */}
                          <td className="px-4 py-4 whitespace-nowrap text-sm font-bold text-brand-dark">
                            {asset.nom_produit}
                          </td>
                          {/* Sécurité (CVE) */}
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-brand-text">
                            {(() => {
                              const cves = asset.alerts.filter(a => a.title.includes('CVE-') || (a.trigger_url && a.trigger_url.startsWith('opencve://')));
                              if (cves.length > 0) {
                                const hasCritical = cves.some(c => c.priority === 'critical' || c.priority === 'high');
                                return (
                                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                                    hasCritical 
                                      ? 'bg-red-50 text-red-700 border border-red-200 animate-pulse' 
                                      : 'bg-orange-50 text-orange-700 border border-orange-200'
                                  }`}>
                                    🛡️ {cves.length} vulnérabilité{cves.length > 1 ? 's' : ''}
                                  </span>
                                );
                              } else {
                                return (
                                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-50 text-green-700 border border-green-200">
                                    ✓ Sain
                                  </span>
                                );
                              }
                            })()}
                          </td>
                          {/* Mises à jour */}
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-brand-text">
                            {(() => {
                              const updates = asset.alerts.filter(a => !a.title.includes('CVE-') && (!a.trigger_url || !a.trigger_url.startsWith('opencve://')));
                              if (updates.length > 0) {
                                return (
                                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-successBg text-brand-success border border-brand-success/20">
                                    📦 {updates.length} mise{updates.length > 1 ? 's' : ''} à jour
                                  </span>
                                );
                              } else {
                                return (
                                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-50 text-gray-600 border border-gray-200">
                                    ✓ À jour
                                  </span>
                                );
                              }
                            })()}
                          </td>
                          {/* Dernière publication */}
                          <td className="px-4 py-4 whitespace-nowrap text-xs font-medium text-brand-text/70">
                            {asset.latest_pub_date ? formatDate(asset.latest_pub_date) : 'N/A'}
                          </td>
                          {/* Responsable */}
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-center">
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-bg text-brand-dark border border-brand-border">
                              {asset.responsable}
                            </span>
                          </td>
                          {/* Actions (stop propagation pour éviter de plier la ligne) */}
                          <td className="px-4 py-4 whitespace-nowrap text-right text-sm" onClick={(e) => e.stopPropagation()}>
                            {(() => {
                              const updateAlert = asset.alerts.find(a => a.priority === 'update_available');
                              const newVersion = updateAlert ? updateAlert.affected_versions : null;
                              return (
                                <button
                                  onClick={() => {
                                    setSelectedAssetForResolution(asset);
                                    const cleanVer = newVersion ? (newVersion.toLowerCase().startsWith('v') ? newVersion.substring(1) : newVersion) : (asset.version_actuelle || '');
                                    setResolutionNewVersion(cleanVer);
                                    setResolutionModalOpen(true);
                                  }}
                                  className="px-3 py-1.5 bg-brand-successBg text-brand-success hover:bg-brand-success/15 border border-brand-success/20 rounded-md text-xs font-semibold transition-all whitespace-nowrap cursor-pointer shadow-sm"
                                >
                                  Valider la mise à jour / Résolu
                                </button>
                              );
                            })()}
                          </td>
                        </tr>

                        {/* Expandable details */}
                        {isExpanded && (
                          <tr className="bg-brand-bg/5">
                            <td colSpan={7} className="px-8 py-4 border-t border-b border-brand-border/60">
                              <div className="bg-white rounded-lg border border-brand-border/60 p-5 shadow-sm space-y-5">
                                {(() => {
                                  const cves = asset.alerts.filter(a => a.title.includes('CVE-') || (a.trigger_url && a.trigger_url.startsWith('opencve://')));
                                  const updates = asset.alerts.filter(a => !a.title.includes('CVE-') && (!a.trigger_url || !a.trigger_url.startsWith('opencve://')));
                                  
                                  const renderAlertList = (alertList) => (
                                    <div className="divide-y divide-brand-border/40 space-y-4">
                                      {alertList.map((alert) => (
                                        <div key={alert.id} className="pt-4 first:pt-0 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                                          <div className="space-y-1 max-w-4xl">
                                            <h4 className="text-sm font-semibold text-brand-text leading-snug">
                                              {alert.title}
                                            </h4>
                                            
                                            {alert.is_secondary === 1 && (
                                              <div className="text-xs text-brand-text/75 mt-1 bg-brand-alert/5 border border-brand-alert/10 px-2.5 py-1 rounded-md">
                                                Produit : {asset.nom_produit} | Source ayant déclenché l'alerte : <a href={alert.trigger_url} target="_blank" rel="noopener noreferrer" className="text-brand-primary hover:underline font-semibold">{alert.trigger_url}</a>
                                              </div>
                                            )}
                                            
                                            {/* Version Details Badge line */}
                                            <div className="flex flex-wrap gap-2 items-center text-xs font-medium py-1.5">
                                              <span className="px-2 py-0.5 rounded bg-brand-bg border border-brand-border text-brand-dark/80 whitespace-nowrap">
                                                Votre version : <span className="font-bold text-brand-dark">{alert.version_actuelle}</span>
                                              </span>
                                              <span className="text-brand-text/30">|</span>
                                              <span className="px-2 py-0.5 rounded bg-brand-bg border border-brand-border text-brand-dark/80 whitespace-nowrap">
                                                Versions impactées : <span className="font-bold text-brand-dark">{alert.affected_versions || 'Non déterminée'}</span>
                                              </span>
                                              {alert.status_text && (
                                                <>
                                                  <span className="text-brand-text/30">|</span>
                                                  <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                                                      alert.priority === 'critical'
                                                      ? 'bg-red-600 text-white border border-red-700 font-extrabold animate-pulse shadow-xs'
                                                      : alert.priority === 'high' 
                                                      ? 'bg-red-50 text-red-700 border border-red-200' 
                                                      : alert.priority === 'update_available'
                                                      ? 'bg-brand-successBg text-brand-success border border-brand-success/20'
                                                      : 'bg-brand-alert/10 text-brand-alert border border-brand-alert/20'
                                                  }`}>
                                                    {alert.status_text}
                                                  </span>
                                                </>
                                              )}
                                            </div>

                                            <div className="flex items-center space-x-3 text-xs text-brand-text/50">
                                              <span>Publié le : {formatDate(alert.pub_date)}</span>
                                              {alert.link && (
                                                <>
                                                  <span>&bull;</span>
                                                  <a 
                                                    href={alert.link} 
                                                    target="_blank" 
                                                    rel="noopener noreferrer" 
                                                    className="text-brand-primary hover:underline font-semibold"
                                                  >
                                                    Consulter la source
                                                  </a>
                                                </>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  );

                                  return (
                                    <>
                                      {cves.length > 0 && (
                                        <div className="space-y-3 pb-3">
                                          <span className="block text-[10px] font-bold text-red-600 uppercase tracking-wider">
                                            🛡️ Vulnérabilités de Sécurité (CVE)
                                          </span>
                                          {renderAlertList(cves)}
                                        </div>
                                      )}
                                      
                                      {updates.length > 0 && (
                                        <div className={`space-y-3 pt-3 ${cves.length > 0 ? 'border-t border-brand-border/40' : ''}`}>
                                          <span className="block text-[10px] font-bold text-brand-primary uppercase tracking-wider">
                                            📦 Mises à jour Logicielles
                                          </span>
                                          {renderAlertList(updates)}
                                        </div>
                                      )}
                                    </>
                                  );
                                })()}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>



      {/* Footer Panel: CERT-FR RSS */}
      <div className="bg-brand-card rounded-lg border border-brand-border shadow-sm">
        <div className="px-6 py-5 border-b border-brand-border bg-white flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-brand-dark">Dernières alertes globales CERT-FR</h3>
            <p className="text-xs text-brand-text/60 mt-0.5">
              Les 5 derniers bulletins officiels publiés par le Centre de cyberdéfense national (CERT-FR).
            </p>
          </div>
          <button 
            onClick={fetchCertAlerts}
            disabled={loadingCert}
            className="p-1.5 text-brand-text/50 hover:text-brand-primary rounded-lg hover:bg-brand-bg transition-colors"
          >
            <svg className={`w-4 h-4 ${loadingCert ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 8H17.5M15 11l-3 3-3-3"></path>
            </svg>
          </button>
        </div>

        <div className="p-6">
          {loadingCert ? (
            <div className="space-y-4 py-2">
              <div className="h-5 bg-brand-bg animate-pulse rounded w-full"></div>
              <div className="h-5 bg-brand-bg animate-pulse rounded w-11/12"></div>
              <div className="h-5 bg-brand-bg animate-pulse rounded w-10/12"></div>
            </div>
          ) : certErrorMessage ? (
            <div className="p-3 bg-brand-alertBg text-brand-alert rounded-lg text-xs font-medium border border-brand-alert/20">
              {certErrorMessage}
            </div>
          ) : certAlerts.length === 0 ? (
            <div className="text-center py-6 text-sm text-brand-text/50 font-medium">
              Aucun bulletin disponible.
            </div>
          ) : (
            <ul className="divide-y divide-brand-border">
              {certAlerts.map((item, index) => (
                <li key={index} className="py-4 first:pt-0 last:pb-0 flex flex-col md:flex-row md:items-center md:justify-between hover:bg-brand-bg/10 px-2 rounded-lg transition-all">
                  <div className="space-y-1 md:max-w-2xl">
                    <h4 className="text-sm font-semibold text-brand-dark line-clamp-1">{item.title}</h4>
                    {item.link && (
                      <a
                        href={item.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-brand-primary hover:underline"
                      >
                        Consulter le bulletin CERT-FR
                      </a>
                    )}
                  </div>
                  <span className="text-xs text-brand-text/50 font-medium mt-1 md:mt-0 whitespace-nowrap self-start md:self-auto">
                    {formatDate(item.pub_date)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Modal de Validation de Mise à jour */}
      {resolutionModalOpen && selectedAssetForResolution && (
        <div className="fixed inset-0 bg-black/45 flex items-center justify-center z-50 animate-none">
          <div className="bg-white rounded-lg border border-brand-border p-6 max-w-md w-full shadow-lg space-y-6">
            <div>
              <h3 className="text-lg font-bold text-brand-dark">
                Valider la mise à jour : {selectedAssetForResolution.nom_produit}
              </h3>
              <p className="text-xs text-brand-text/60 mt-1">
                Veuillez confirmer la nouvelle version installée pour cet actif. Cela résoudra toutes les alertes de sécurité en cours et l'enregistrera dans l'historique.
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-[10px] font-bold text-brand-dark uppercase tracking-wider mb-2">
                  Nouvelle version de l'actif
                </label>
                <input
                  type="text"
                  required
                  value={resolutionNewVersion}
                  onChange={(e) => setResolutionNewVersion(e.target.value)}
                  placeholder="Ex: 5.4.7 ou 1.2.0"
                  className="w-full px-4 py-2.5 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary font-medium"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 border-t border-brand-border pt-4">
              <button
                type="button"
                onClick={() => {
                  setResolutionModalOpen(false);
                  setSelectedAssetForResolution(null);
                }}
                className="px-4 py-2 text-xs font-semibold text-brand-text/75 hover:bg-brand-bg rounded-lg transition-all"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={() => {
                  handleResolveAssetAlerts(selectedAssetForResolution.asset_id, resolutionNewVersion);
                  setResolutionModalOpen(false);
                  setSelectedAssetForResolution(null);
                }}
                className="px-4 py-2 bg-brand-primary text-white text-xs font-semibold rounded-lg hover:bg-brand-primary/95 transition-all shadow-sm"
              >
                Valider la mise à jour
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
