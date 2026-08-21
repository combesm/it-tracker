import React, { useState, useEffect } from 'react';

export default function History({ backendUrl }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('all'); // 'all', 'updates', 'cve'
  const [cancellingId, setCancellingId] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    setCurrentPage(1);
  }, [search, filterType]);

  const formatDate = (dateStr) => {
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

  const parseTimestamp = (dateStr) => {
    if (!dateStr) return 0;
    // Format DD/MM/YYYY HH:MM
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

    if (title.startsWith('mise à jour disponible')) {
      return false;
    }

    const securityKeywords = [
      'cve-', 'certfr-', 'cvss', 'vulnérabilité', 'vulnerabilite', 
      'faille', 'sécurité', 'securite', 'exploit', 'advisory', 'patch de sécurité'
    ];
    return securityKeywords.some(kw => full.includes(kw));
  };

  const fetchData = async () => {
    try {
      setLoading(true);
      const [resLogs, resAlerts] = await Promise.all([
        fetch(`${backendUrl}/api/update-logs`),
        fetch(`${backendUrl}/api/alerts/resolved`)
      ]);

      let logsList = [];
      let alertsList = [];

      if (resLogs.ok) {
        const logsData = await resLogs.json();
        logsList = logsData.map(l => ({
          ...l,
          uniqueKey: `update-${l.id}`,
          itemType: 'update',
          dateDisplay: l.date_maj || 'N/A',
          sortTime: parseTimestamp(l.date_maj)
        }));
      }

      if (resAlerts.ok) {
        const alertsData = await resAlerts.json();
        const cveAlerts = alertsData.filter(a => isSecurityAlert(a));
        alertsList = cveAlerts.map(a => {
          const dateVal = a.resolved_at || a.pub_date;
          return {
            ...a,
            uniqueKey: `cve-${a.id}`,
            itemType: 'cve',
            dateDisplay: formatDate(dateVal),
            sortTime: parseTimestamp(dateVal)
          };
        });
      }

      // Fusion et tri STRICTEMENT chronologique (du plus récent au plus ancien)
      const merged = [...logsList, ...alertsList];
      merged.sort((a, b) => (b.sortTime || 0) - (a.sortTime || 0));
      setItems(merged);
    } catch (err) {
      console.error("Erreur lors de la récupération du journal d'historique:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelResolution = async (alertId) => {
    try {
      setCancellingId(`alert-${alertId}`);
      const res = await fetch(`${backendUrl}/api/alerts/reactivate/${alertId}`, {
        method: 'POST'
      });
      if (res.ok) {
        await fetchData();
      }
    } catch (err) {
      console.error("Erreur lors de l'annulation de la résolution:", err);
    } finally {
      setCancellingId(null);
    }
  };

  const handleRevertUpdate = async (logId) => {
    try {
      setCancellingId(`update-${logId}`);
      const res = await fetch(`${backendUrl}/api/update-logs/revert/${logId}`, {
        method: 'POST'
      });
      if (res.ok) {
        await fetchData();
      } else {
        alert("Impossible d'annuler cette mise à jour.");
      }
    } catch (err) {
      console.error("Erreur lors de l'annulation de la mise à jour:", err);
    } finally {
      setCancellingId(null);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const filteredItems = items.filter(item => {
    if (filterType === 'updates' && item.itemType !== 'update') return false;
    if (filterType === 'cve' && item.itemType !== 'cve') return false;

    if (!search.trim()) return true;
    const query = search.toLowerCase();

    const nameMatch = (item.nom_produit || '').toLowerCase().includes(query);
    const titleMatch = (item.title || '').toLowerCase().includes(query);
    const oldVerMatch = (item.ancienne_version || '').toLowerCase().includes(query);
    const newVerMatch = (item.nouvelle_version || '').toLowerCase().includes(query);
    const resVerMatch = (item.resolved_at_version || '').toLowerCase().includes(query);
    const resolverMatch = (item.resolved_by || item.responsable || '').toLowerCase().includes(query);
    const dateMatch = (item.dateDisplay || '').toLowerCase().includes(query);

    return nameMatch || titleMatch || oldVerMatch || newVerMatch || resVerMatch || resolverMatch || dateMatch;
  });

  const updatesCount = items.filter(i => i.itemType === 'update').length;
  const cveCount = items.filter(i => i.itemType === 'cve').length;

  const itemsPerPage = 50;
  const totalItems = filteredItems.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage);

  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;

  const displayedItems = filteredItems.slice(startIndex, endIndex);

  const getPageNumbers = () => {
    const pages = [];
    const maxVisible = 5;
    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      pages.push(1);
      let start = Math.max(2, currentPage - 1);
      let end = Math.min(totalPages - 1, currentPage + 1);

      if (currentPage <= 3) end = 4;
      if (currentPage >= totalPages - 2) start = totalPages - 3;

      if (start > 2) pages.push('...');
      for (let i = start; i <= end; i++) pages.push(i);
      if (end < totalPages - 1) pages.push('...');
      pages.push(totalPages);
    }
    return pages;
  };

  return (
    <div className="space-y-6">
      {/* Tab Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-brand-dark">Journal et Historique Unifié</h1>
          <p className="text-sm text-brand-text/70 mt-1">
            Fil d'actualité chronologique distinguant les mises à jour de version installées des failles de sécurité (CVE) résolues.
          </p>
        </div>
        <button
          onClick={fetchData}
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

      {/* Filter Pills & Search */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center space-x-2 border-b border-brand-border md:border-b-0 pb-2 md:pb-0">
          <button
            onClick={() => setFilterType('all')}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              filterType === 'all'
                ? 'bg-brand-primary text-white shadow-sm font-bold'
                : 'bg-brand-bg text-brand-text/75 hover:text-brand-dark hover:bg-brand-border/40'
            }`}
          >
            Tous les événements ({items.length})
          </button>
          <button
            onClick={() => setFilterType('updates')}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              filterType === 'updates'
                ? 'bg-blue-600 text-white shadow-sm font-bold'
                : 'bg-blue-50 text-blue-800 hover:bg-blue-100'
            }`}
          >
            📦 Mises à jour de version ({updatesCount})
          </button>
          <button
            onClick={() => setFilterType('cve')}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              filterType === 'cve'
                ? 'bg-red-600 text-white shadow-sm font-bold'
                : 'bg-red-50 text-red-800 hover:bg-red-100'
            }`}
          >
            🛡️ Failles & CVEs ({cveCount})
          </button>
        </div>

        {/* Search Bar */}
        <div className="max-w-xs w-full">
          <div className="relative">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher par actif, CVE, résolveur..."
              className="w-full px-4 py-2 pl-9 text-xs border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary bg-white text-brand-dark font-medium"
            />
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <svg className="w-3.5 h-3.5 text-brand-text/40" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
              </svg>
            </div>
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-brand-text/40 hover:text-brand-dark cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            )}
          </div>
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
          ) : filteredItems.length === 0 ? (
            <div className="text-center py-12 text-sm text-brand-text/50 font-medium italic bg-brand-bg/10 rounded-lg border border-dashed border-brand-border">
              {search ? 'Aucun événement ne correspond à votre recherche.' : 'Aucun événement enregistré dans l\'historique.'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-brand-border">
                <thead>
                  <tr className="bg-brand-bg/50">
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Type & Date</th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Actif</th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Détails de l'événement</th>
                    <th scope="col" className="px-4 py-3 text-center text-xs font-bold text-brand-dark uppercase tracking-wider">Résolveur</th>
                    <th scope="col" className="px-4 py-3 text-right text-xs font-bold text-brand-dark uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-brand-border text-xs">
                  {displayedItems.map((item) => (
                    <tr key={item.uniqueKey} className="hover:bg-brand-bg/10 transition-colors">
                      {/* Type & Date */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        {item.itemType === 'update' ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                            📦 Mise à jour
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-red-50 text-red-700 border border-red-200">
                            🛡️ Faille / CVE
                          </span>
                        )}
                        <div className="text-[11px] text-brand-text/60 font-medium mt-1">
                          {item.dateDisplay}
                        </div>
                      </td>

                      {/* Actif */}
                      <td className="px-4 py-3 whitespace-nowrap font-semibold text-brand-dark">
                        {item.nom_produit}
                      </td>

                      {/* Détails */}
                      <td className="px-4 py-3">
                        {item.itemType === 'update' ? (
                          <div className="text-brand-dark text-xs">
                            <span className="text-brand-text/60">Passage de </span>
                            <span className="font-mono font-semibold text-brand-dark">{item.ancienne_version || 'N/A'}</span>
                            <span className="text-brand-text/60"> à </span>
                            <span className="font-mono font-bold text-brand-primary">{item.nouvelle_version}</span>
                          </div>
                        ) : (
                          <div>
                            <div className="text-xs text-brand-dark font-semibold line-clamp-1 max-w-md" title={item.title}>
                              {item.title}
                            </div>
                            <div className="text-[11px] text-brand-text/60 font-mono mt-0.5">
                              Résolu en version : <span className="font-semibold text-brand-dark">{item.resolved_at_version || 'N/A'}</span>
                            </div>
                          </div>
                        )}
                      </td>

                      {/* Résolveur */}
                      <td className="px-4 py-3 whitespace-nowrap text-center">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-bg text-brand-dark border border-brand-border">
                          {item.resolved_by || item.responsable || 'N/A'}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3 whitespace-nowrap text-right">
                        {item.itemType === 'cve' ? (
                          <button
                            onClick={() => handleCancelResolution(item.id)}
                            disabled={cancellingId === `alert-${item.id}`}
                            className="px-2.5 py-1 text-[11px] font-semibold text-red-600 hover:text-white hover:bg-red-600 border border-red-600 rounded-md transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {cancellingId === `alert-${item.id}` ? 'Annulation...' : 'Annuler la résolution'}
                          </button>
                        ) : (
                          <button
                            onClick={() => handleRevertUpdate(item.id)}
                            disabled={cancellingId === `update-${item.id}`}
                            className="px-2.5 py-1 text-[11px] font-semibold text-amber-700 hover:text-white hover:bg-amber-600 border border-amber-600/40 rounded-md transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                            title={`Remettre l'actif en version ${item.ancienne_version || 'précédente'}`}
                          >
                            {cancellingId === `update-${item.id}` ? 'Annulation...' : 'Annuler la mise à jour'}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination Controls */}
          {!loading && totalPages > 1 && (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-6 pt-6 border-t border-brand-border">
              <div className="text-xs text-brand-text/60 font-medium">
                Affichage de <span className="font-semibold text-brand-dark">{startIndex + 1}</span> à{" "}
                <span className="font-semibold text-brand-dark">{Math.min(endIndex, totalItems)}</span> sur{" "}
                <span className="font-semibold text-brand-dark">{totalItems}</span> événements
              </div>
              <div className="flex items-center space-x-1">
                <button
                  onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                  disabled={currentPage === 1}
                  className="px-3 py-1.5 text-xs font-semibold rounded-md border border-brand-border bg-white text-brand-dark hover:bg-brand-bg/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  Précédent
                </button>
                
                {getPageNumbers().map((page, index) => {
                  if (page === '...') {
                    return (
                      <span key={`ellipsis-${index}`} className="px-2 py-1.5 text-xs font-medium text-brand-text/40">
                        ...
                      </span>
                    );
                  }
                  return (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={`px-3 py-1.5 text-xs rounded-md transition-colors cursor-pointer ${
                        currentPage === page
                          ? 'bg-brand-primary text-white font-bold border border-brand-primary shadow-sm'
                          : 'border border-brand-border bg-white text-brand-text/80 hover:bg-brand-bg/50 hover:text-brand-dark font-medium'
                      }`}
                    >
                      {page}
                    </button>
                  );
                })}
                
                <button
                  onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                  disabled={currentPage === totalPages}
                  className="px-3 py-1.5 text-xs font-semibold rounded-md border border-brand-border bg-white text-brand-dark hover:bg-brand-bg/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  Suivant
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
