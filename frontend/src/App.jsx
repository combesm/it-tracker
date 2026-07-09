import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import Assets from './components/Assets';
import Team from './components/Team';

// Utiliser localhost:5000 en dev, et l'origine courante en prod (servie par Flask)
const BACKEND_URL = import.meta.env.DEV ? 'http://localhost:5000' : '';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  // Compteur fictif pour forcer le rafraîchissement des formulaires liés à l'équipe
  const [teamRefreshKey, setTeamRefreshKey] = useState(0);

  const handleTeamChange = () => {
    setTeamRefreshKey(prev => prev + 1);
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard backendUrl={BACKEND_URL} />;
      case 'assets':
        return <Assets backendUrl={BACKEND_URL} key={`assets-ref-${teamRefreshKey}`} />;
      case 'team':
        return <Team backendUrl={BACKEND_URL} onTeamChange={handleTeamChange} />;
      default:
        return <Dashboard backendUrl={BACKEND_URL} />;
    }
  };

  return (
    <div className="min-h-screen bg-brand-bg text-brand-text font-sans">
      {/* Sidebar de navigation latérale fixe */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Zone de contenu principale décalée à droite de la Sidebar */}
      <main className="pl-64 min-h-screen">
        <div className="max-w-7xl mx-auto px-8 py-8">
          {renderContent()}
        </div>
      </main>
    </div>
  );
}
