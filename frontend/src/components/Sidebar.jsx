import React from 'react';

export default function Sidebar({ activeTab, setActiveTab }) {
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
    }
  ];

  return (
    <aside className="fixed inset-y-0 left-0 w-64 bg-brand-dark text-white flex flex-col z-20 border-r border-brand-border/10">
      {/* Sidebar Header */}
      <div className="h-16 flex items-center px-6 border-b border-brand-border/10 bg-brand-dark">
        <img src="/logo.png" alt="Herakles" className="h-8 w-auto object-contain" />
        <span className="ml-3 text-sm font-bold tracking-wider text-white/90 uppercase">
          IT Tracker
        </span>
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
      </nav>

      {/* Sidebar Footer */}
      <div className="p-4 border-t border-brand-border/10 text-center bg-brand-dark/50">
        <span className="text-xs text-white/50 block font-medium">
          Version 1.0.0
        </span>
        <span className="text-[10px] text-white/40 block mt-1">
          &copy; 2026 Herakles PME
        </span>
      </div>
    </aside>
  );
}
