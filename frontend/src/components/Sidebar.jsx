import React from 'react';

const OPENCVE_URL = '/opencve/cve';

export default function Sidebar({ activeTab, setActiveTab, onExport, onLogout }) {
  const menuItems = [
    {
      id: 'dashboard',
      label: 'Tableau de bord',
      icon: (
        <svg className="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z"></path>
        </svg>
      )
    },
    {
      id: 'assets',
      label: 'Actifs & Services',
      icon: (
        <svg className="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
        </svg>
      )
    },
    {
      id: 'team',
      label: "Gestion de l'Équipe",
      icon: (
        <svg className="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>
        </svg>
      )
    },
    {
      id: 'history',
      label: 'Logs',
      icon: (
        <svg className="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
      )
    }
  ];

  const openCVEItem = {
    id: 'opencve',
    label: 'OpenCVE',
    url: OPENCVE_URL,
    icon: (
      <svg className="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
      </svg>
    )
  };

  return (
    <aside className="fixed inset-y-0 left-0 w-64 bg-brand-dark text-white flex flex-col z-20 border-r border-brand-border/10">
      {/* Sidebar Header */}
      <div className="h-20 flex items-center justify-center px-4 border-b border-brand-border/10 bg-brand-dark">
        <img src="/logo.png" alt="Herakles Groupe" className="h-12 w-auto max-w-full object-contain" />
      </div>

      {/* Navigation Menu */}
      <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
        {menuItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors duration-150 ${
                isActive
                  ? 'bg-brand-primary text-white shadow-sm'
                  : 'text-white/75 hover:bg-white/5 hover:text-white'
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          );
        })}

        {/* Lien externe OpenCVE */}
        <a
          href={openCVEItem.url}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors duration-150 text-white/75 hover:bg-white/5 hover:text-white"
        >
          {openCVEItem.icon}
          {openCVEItem.label}
          <svg className="w-3 h-3 ml-auto opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
          </svg>
        </a>
      </nav>

      {/* Action: Export Excel */}
      <div className="px-4 py-4 border-t border-brand-border/10 bg-brand-dark/30">
        <button
          onClick={onExport}
          className="w-full flex items-center justify-center px-4 py-2.5 text-xs font-semibold rounded-lg text-white transition-all shadow-sm cursor-pointer"
          style={{ backgroundColor: '#1D6F42', hover: 'none' }}
          onMouseEnter={e => e.currentTarget.style.backgroundColor = '#155230'}
          onMouseLeave={e => e.currentTarget.style.backgroundColor = '#1D6F42'}
        >
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
          </svg>
          Exporter en Excel
        </button>
      </div>

      {/* Action: Déconnexion */}
      <div className="px-4 py-2 border-t border-brand-border/10">
        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center px-4 py-2 text-xs font-semibold rounded-lg bg-red-600/20 hover:bg-red-600/35 text-red-300 hover:text-white transition-all cursor-pointer"
        >
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
          </svg>
          Se déconnecter
        </button>
      </div>

      {/* Sidebar Footer */}
      <div className="p-4 border-t border-brand-border/10 text-center bg-brand-dark/50">
        <span className="text-[10px] text-white/40 block">
          &copy; 2026 combesm
        </span>
      </div>
    </aside>
  );
}
