import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import Assets from './components/Assets';
import Team from './components/Team';
import History from './components/History';
import Login from './components/Login';
import Settings from './components/Settings';

// Utiliser localhost:5000 en dev, et l'origine courante en prod (servie par Flask)
const BACKEND_URL = import.meta.env.DEV ? 'http://localhost:5000' : '';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('tracker_token'));
  const [activeTab, setActiveTab] = useState('dashboard');
  // Compteur fictif pour forcer le rafraîchissement des formulaires liés à l'équipe
  const [teamRefreshKey, setTeamRefreshKey] = useState(0);
  const [config, setConfig] = useState({ enable_uptime_kuma: false, enable_opencve: false, enable_vigil365: false });

  useEffect(() => {
    const handleAuthFailed = () => {
      setToken(null);
    };
    window.addEventListener('auth-failed', handleAuthFailed);

    fetch(`${BACKEND_URL}/api/config`)
      .then(res => {
        if (res.ok) return res.json();
        throw new Error('Failed to load config');
      })
      .then(data => setConfig(data))
      .catch(err => console.error("Error loading config:", err));

    return () => window.removeEventListener('auth-failed', handleAuthFailed);
  }, []);

  const handleLogout = async () => {
    try {
      await fetch(`${BACKEND_URL}/api/logout`, { method: 'POST' });
    } catch (err) {
      console.error("Logout failed:", err);
    }
    localStorage.removeItem('tracker_token');
    localStorage.removeItem('tracker_username');
    setToken(null);
  };

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
      case 'history':
        return <History backendUrl={BACKEND_URL} />;
      case 'settings':
        return <Settings backendUrl={BACKEND_URL} />;
      default:
        return <Dashboard backendUrl={BACKEND_URL} />;
    }
  };

  if (!token) {
    return <Login backendUrl={BACKEND_URL} onLoginSuccess={(t) => setToken(t)} />;
  }

  return (
    <div className="min-h-screen bg-brand-bg text-brand-text font-sans">
      {/* Sidebar de navigation latérale fixe avec prop de déconnexion */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} onLogout={handleLogout} config={config} />

      {/* Zone de contenu principale décalée à droite de la Sidebar */}
      <main className="pl-64 min-h-screen">
        <div className="max-w-7xl mx-auto px-8 py-8">
          {renderContent()}
        </div>
      </main>
    </div>
  );
}
