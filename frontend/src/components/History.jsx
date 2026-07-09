import React, { useState, useEffect } from 'react';

export default function History({ backendUrl }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

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

  useEffect(() => {
    fetchLogs();
  }, []);

  // Filtrer les logs par nom de produit, ancienne version ou nouvelle version
  const filteredLogs = logs.filter(log => {
    const query = search.toLowerCase();
    const nameMatch = (log.nom_produit || '').toLowerCase().includes(query);
    const oldVerMatch = (log.ancienne_version || '').toLowerCase().includes(query);
    const newVerMatch = (log.nouvelle_version || '').toLowerCase().includes(query);
    return nameMatch || oldVerMatch || newVerMatch;
  });

  return (
    <div className="space-y-6">
      {/* Tab Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-brand-dark">Historique des mises à jour</h1>
          <p className="text-sm text-brand-text/70 mt-1">
            Journal des versions de vos actifs informatiques consignées en base de données.
          </p>
        </div>
        <button
          onClick={fetchLogs}
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

      {/* Search Bar */}
      <div className="max-w-md">
        <div className="relative">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher un actif, une version (ex: Joomla, 5.4.7)..."
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

      {/* Simple Logs Table */}
      <div className="bg-brand-card rounded-lg border border-brand-border shadow-sm overflow-hidden">
        <div className="p-6">
          {loading ? (
            <div className="space-y-4 py-2">
              <div className="h-5 bg-brand-bg animate-pulse rounded w-full"></div>
              <div className="h-5 bg-brand-bg animate-pulse rounded w-11/12"></div>
            </div>
          ) : filteredLogs.length === 0 ? (
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
          )}
        </div>
      </div>
    </div>
  );
}
