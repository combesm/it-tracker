import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import Assets from './components/Assets';
import Team from './components/Team';
import History from './components/History';
import Login from './components/Login';
import Settings from './components/Settings';
import * as XLSX from 'xlsx';

// Utiliser localhost:5000 en dev, et l'origine courante en prod (servie par Flask)
const BACKEND_URL = import.meta.env.DEV ? 'http://localhost:5000' : '';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('tracker_token'));
  const [activeTab, setActiveTab] = useState('dashboard');
  // Compteur fictif pour forcer le rafraîchissement des formulaires liés à l'équipe
  const [teamRefreshKey, setTeamRefreshKey] = useState(0);
  const [config, setConfig] = useState({ enable_uptime_kuma: false, enable_opencve: false });

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

  const handleExportExcel = async () => {
    try {
      // 1. Récupération des Actifs
      const resAssets = await fetch(`${BACKEND_URL}/api/assets`);
      const assets = resAssets.ok ? await resAssets.json() : [];

      // 2. Récupération de l'Équipe
      const resTeam = await fetch(`${BACKEND_URL}/api/team`);
      const team = resTeam.ok ? await resTeam.json() : [];

      // 3. Récupération des Alertes Actives
      const resAlerts = await fetch(`${BACKEND_URL}/api/alerts`);
      const alerts = resAlerts.ok ? await resAlerts.json() : [];

      // Initialiser le classeur Excel
      const wb = XLSX.utils.book_new();

      // Onglet 1 : Actifs & Services
      const assetsData = assets.map(a => ({
        "Nom du produit": a.nom_produit,
        "Entités": a.entites || 'Groupe',
        "Fournisseur": a.fournisseur || '',
        "Version actuelle": a.version_actuelle,
        "Type de déploiement": a.type_deploiement,
        "Hébergement / Machine": a.machine_hebergement || '',
        "Type de licence": a.type_licence || 'Perpétuelle',
        "Date d'expiration": a.date_expiration ? new Date(a.date_expiration).toLocaleDateString('fr-FR') : '',
        "Responsable (Trigramme)": a.responsable,
        "Email Responsable": a.email_responsable || '',
        "Flux RSS": a.url_rss || ''
      }));
      const wsAssets = XLSX.utils.json_to_sheet(assetsData);
      XLSX.utils.book_append_sheet(wb, wsAssets, "Actifs & Services");

      // Onglet 2 : Membres de l'Équipe
      const teamData = team.map(t => ({
        "Trigramme": t.trigramme,
        "Adresse Email": t.email
      }));
      const wsTeam = XLSX.utils.json_to_sheet(teamData);
      XLSX.utils.book_append_sheet(wb, wsTeam, "Membres de l'Équipe");

      // Onglet 3 : Alertes de Sécurité
      const alertsData = alerts.map(al => ({
        "Actif concerné": al.nom_produit,
        "Alerte / Faille": al.title,
        "Date de publication": al.pub_date ? new Date(al.pub_date).toLocaleDateString('fr-FR') : '',
        "Responsable": al.responsable,
        "Lien source": al.link || ''
      }));
      const wsAlerts = XLSX.utils.json_to_sheet(alertsData);
      XLSX.utils.book_append_sheet(wb, wsAlerts, "Alertes Actives");

      // Télécharger le fichier Excel
      XLSX.writeFile(wb, "Inventaire_IT_Herakles.xlsx");
    } catch (err) {
      console.error("Erreur lors de l'export Excel:", err);
      alert("Une erreur est survenue lors de la génération du fichier Excel.");
    }
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
      {/* Sidebar de navigation latérale fixe avec prop d'export et de déconnexion */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} onExport={handleExportExcel} onLogout={handleLogout} config={config} />

      {/* Zone de contenu principale décalée à droite de la Sidebar */}
      <main className="pl-64 min-h-screen">
        <div className="max-w-7xl mx-auto px-8 py-8">
          {renderContent()}
        </div>
      </main>
    </div>
  );
}
