import React, { useState, useEffect } from 'react';

export default function History({ backendUrl }) {
  const [logs, setLogs] = useState([]);
  const [resolvedAlerts, setResolvedAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeSubTab, setActiveSubTab] = useState('updates'); // 'updates' or 'resolved'
  const [cancellingId, setCancellingId] = useState(null);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${backendUrl}/api/update-logs`);
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (err) {
      console.error("Erreur lors de la récupération de l'historique:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchResolvedAlerts = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${backendUrl}/api/alerts/resolved`);
      if (res.ok) {
        const data = await res.json();
        setResolvedAlerts(data);
      }
    } catch (err) {
      console.error("Erreur lors de la récupération des alertes résolues:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelResolution = async (alertId) => {
    try {
      setCancellingId(alertId);
      const res = await fetch(`${backendUrl}/api/alerts/reactivate/${alertId}`, {
        method: 'POST'
      });
      if (res.ok) {
        await fetchResolvedAlerts();
      }
    } catch (err) {
      console.error("Erreur lors de l'annulation de la résolution:", err);
    } finally {
      setCancellingId(null);
    }
  };

  const handleRefresh = () => {
    if (activeSubTab === 'updates') {
      fetchLogs();
    } else {
      fetchResolvedAlerts();
    }
  };

  useEffect(() => {
    handleRefresh();
  }, [activeSubTab]);

  const filteredLogs = logs.filter(log => {
    const query = search.toLowerCase();
    const nameMatch = (log.nom_produit || '').toLowerCase().includes(query);
    const oldVerMatch = (log.ancienne_version || '').toLowerCase().includes(query);
    const newVerMatch = (log.nouvelle_version || '').toLowerCase().includes(query);
    return nameMatch || oldVerMatch || newVerMatch;
  });

  const filteredResolvedAlerts = resolvedAlerts.filter(alert => {
    const query = search.toLowerCase();
    const nameMatch = (alert.nom_produit || '').toLowerCase().includes(query);
    const titleMatch = (alert.title || '').toLowerCase().includes(query);
    const verMatch = (alert.resolved_at_version || '').toLowerCase().includes(query);
    return nameMatch || titleMatch || verMatch;
  });

  return (
    <div className="space-y-6">
      {/* Tab Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-brand-dark">Logs et Historique</h1>
          <p className="text-sm text-brand-text/70 mt-1">
            Journal des versions et des résolutions d'alertes de sécurité consignées en base de données.
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="px-4 py-2 text-xs font-semibold rounded-lg bg-brand-primary text-white hover:bg-brand-primary/95 transition-all flex items-center shadow-sm cursor-pointer self-start md:self-auto"
        >
          {loading ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Actualisation...
            </>
          ) : (
            'Actualiser'
          )}
        </button>
      </div>

      {/* Sub-tabs toggle */}
      <div className="flex border-b border-brand-border">
        <button
          onClick={() => {
            setSearch('');
            setActiveSubTab('updates');
          }}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-all cursor-pointer ${
            activeSubTab === 'updates'
              ? 'border-brand-primary text-brand-primary'
              : 'border-transparent text-brand-text/60 hover:text-brand-dark'
          }`}
        >
          Historique des Mises à jour
        </button>
        <button
          onClick={() => {
            setSearch('');
            setActiveSubTab('resolved');
          }}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-all cursor-pointer ${
            activeSubTab === 'resolved'
              ? 'border-brand-primary text-brand-primary'
              : 'border-transparent text-brand-text/60 hover:text-brand-dark'
          }`}
        >
          Alertes résolues (Logs de résolutions)
        </button>
      </div>

      {/* Search Bar */}
      <div className="max-w-md">
        <div className="relative">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={
              activeSubTab === 'updates'
                ? "Rechercher un actif, une version (ex: Joomla, 5.4.7)..."
                : "Rechercher une alerte, une CVE ou un actif..."
            }
            className="w-full px-4 py-2.5 pl-10 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary bg-white text-brand-dark"
          />
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
            <svg className="w-4 h-4 text-brand-text/40" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
          </div>
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-brand-text/40 hover:text-brand-dark"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Logs Table */}
      <div className="bg-brand-card rounded-lg border border-brand-border shadow-sm overflow-hidden">
        <div className="p-6">
          {loading ? (
            <div className="space-y-4 py-2">
              <div className="h-5 bg-brand-bg animate-pulse rounded w-full"></div>
              <div className="h-5 bg-brand-bg animate-pulse rounded w-11/12"></div>
            </div>
          ) : activeSubTab === 'updates' ? (
            filteredLogs.length === 0 ? (
              <div className="text-center py-12 text-sm text-brand-text/50 font-medium italic bg-brand-bg/10 rounded-lg border border-dashed border-brand-border">
                {search ? 'Aucun résultat ne correspond à votre recherche.' : 'Aucun historique de mise à jour disponible.'}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-brand-border">
                  <thead>
                    <tr className="bg-brand-bg/50">
                      <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Date & Heure</th>
                      <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Actif</th>
                      <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Ancienne Version</th>
                      <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Nouvelle Version</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-brand-border text-xs">
                    {filteredLogs.map((log) => (
                      <tr key={log.id} className="hover:bg-brand-bg/10 transition-colors">
                        <td className="px-4 py-3 whitespace-nowrap text-brand-text/60 font-medium">{log.date_maj}</td>
                        <td className="px-4 py-3 whitespace-nowrap font-semibold text-brand-dark">{log.nom_produit}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-brand-text/75">{log.ancienne_version || 'N/A'}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-brand-dark font-semibold">{log.nouvelle_version}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          ) : (
            filteredResolvedAlerts.length === 0 ? (
              <div className="text-center py-12 text-sm text-brand-text/50 font-medium italic bg-brand-bg/10 rounded-lg border border-dashed border-brand-border">
                {search ? 'Aucun résultat ne correspond à votre recherche.' : 'Aucun log de résolution d\'alerte disponible.'}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-brand-border">
                  <thead>
                    <tr className="bg-brand-bg/50">
                      <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Actif</th>
                      <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Alerte / CVE</th>
                      <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Version de résolution</th>
                      <th scope="col" className="px-4 py-3 text-right text-xs font-bold text-brand-dark uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-brand-border text-xs">
                    {filteredResolvedAlerts.map((alert) => (
                      <tr key={alert.id} className="hover:bg-brand-bg/10 transition-colors">
                        <td className="px-4 py-3 whitespace-nowrap font-semibold text-brand-dark">{alert.nom_produit}</td>
                        <td className="px-4 py-3 text-brand-text/75 font-medium max-w-sm truncate" title={alert.title}>
                          {alert.title}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-brand-dark font-mono font-semibold">
                          {alert.resolved_at_version || 'N/A'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-right">
                          <button
                            onClick={() => handleCancelResolution(alert.id)}
                            disabled={cancellingId === alert.id}
                            className="px-2.5 py-1 text-[11px] font-semibold text-red-600 hover:text-white hover:bg-red-600 border border-red-600 rounded-md transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {cancellingId === alert.id ? 'Annulation...' : 'Annuler la résolution'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
