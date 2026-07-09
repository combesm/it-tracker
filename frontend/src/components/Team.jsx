import React, { useState, useEffect } from 'react';

export default function Team({ backendUrl, onTeamChange }) {
  const [team, setTeam] = useState([]);
  const [loading, setLoading] = useState(true);
  const [trigramme, setTrigramme] = useState('');
  const [email, setEmail] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const fetchTeam = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${backendUrl}/api/team`);
      if (res.ok) {
        const data = await res.json();
        setTeam(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTeam();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    const cleanTrigramme = trigramme.trim().toUpperCase();
    const cleanEmail = email.trim();

    if (!cleanTrigramme || !cleanEmail) {
      setErrorMessage("Tous les champs sont obligatoires.");
      return;
    }

    if (cleanTrigramme.length !== 3) {
      setErrorMessage("Le trigramme doit comporter exactement 3 lettres (ex: MUC).");
      return;
    }

    try {
      const res = await fetch(`${backendUrl}/api/team`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trigramme: cleanTrigramme, email: cleanEmail })
      });

      if (res.ok) {
        setTrigramme('');
        setEmail('');
        setSuccessMessage(`Le responsable ${cleanTrigramme} a été ajouté avec succès.`);
        fetchTeam();
        if (onTeamChange) onTeamChange(); // Notifier pour mettre à jour la liste des responsables
      } else {
        const data = await res.json();
        setErrorMessage(data.error || "Une erreur est survenue lors de la création.");
      }
    } catch (err) {
      setErrorMessage("Erreur de connexion avec le serveur.");
      console.error(err);
    }
  };

  const handleDelete = async (memberTrigramme) => {
    setErrorMessage('');
    setSuccessMessage('');
    
    if (!confirm(`Êtes-vous sûr de vouloir supprimer le responsable ${memberTrigramme} ?`)) {
      return;
    }

    try {
      const res = await fetch(`${backendUrl}/api/team/${memberTrigramme}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        setSuccessMessage(`Le responsable ${memberTrigramme} a été supprimé.`);
        fetchTeam();
        if (onTeamChange) onTeamChange();
      } else {
        const data = await res.json();
        setErrorMessage(data.error || "Impossible de supprimer ce responsable.");
      }
    } catch (err) {
      setErrorMessage("Erreur de réseau lors de la suppression.");
      console.error(err);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-brand-dark">Gestion de l'Équipe</h1>
        <p className="text-sm text-brand-text/70 mt-1">
          Registre des administrateurs et responsables des différents actifs informatiques.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left column: Add Member Form */}
        <div className="bg-brand-card rounded-lg border border-brand-border shadow-sm p-6 self-start">
          <h3 className="text-base font-bold text-brand-dark border-b border-brand-border pb-3 mb-4">
            Ajouter un responsable
          </h3>

          {errorMessage && (
            <div className="p-3 bg-brand-alertBg text-brand-alert rounded-lg text-xs font-semibold border border-brand-alert/20 mb-4">
              {errorMessage}
            </div>
          )}

          {successMessage && (
            <div className="p-3 bg-brand-successBg text-brand-success rounded-lg text-xs font-semibold border border-brand-success/20 mb-4">
              {successMessage}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">
                Trigramme *
              </label>
              <input
                type="text"
                required
                maxLength={3}
                value={trigramme}
                onChange={(e) => setTrigramme(e.target.value.slice(0, 3))}
                className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary uppercase"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">
                Adresse Email *
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary"
              />
            </div>

            <button
              type="submit"
              className="w-full py-2 bg-brand-primary text-white text-xs font-semibold rounded-lg hover:bg-brand-primary/95 transition-all shadow-sm flex items-center justify-center"
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"></path>
              </svg>
              Enregistrer
            </button>
          </form>
        </div>

        {/* Right columns: Team Registry Table */}
        <div className="bg-brand-card rounded-lg border border-brand-border shadow-sm p-6 lg:col-span-2">
          <h3 className="text-base font-bold text-brand-dark border-b border-brand-border pb-3 mb-4">
            Registre des responsables
          </h3>

          {loading ? (
            <div className="space-y-3 py-4">
              <div className="h-6 bg-brand-bg animate-pulse rounded"></div>
              <div className="h-6 bg-brand-bg animate-pulse rounded"></div>
            </div>
          ) : team.length === 0 ? (
            <div className="text-center py-8">
              <span className="text-sm text-brand-text/50 font-medium">
                Aucun responsable enregistré. Utilisez le formulaire pour en ajouter.
              </span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-brand-border">
                <thead>
                  <tr className="bg-brand-bg/50">
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Trigramme</th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Email</th>
                    <th scope="col" className="relative px-4 py-3 text-right">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-brand-border">
                  {team.map((member) => (
                    <tr key={member.trigramme} className="hover:bg-brand-bg/25 transition-colors">
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-bold text-brand-dark">
                        <span className="px-2.5 py-1 bg-brand-bg border border-brand-border rounded">
                          {member.trigramme}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-brand-text font-medium">
                        {member.email}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-right text-xs font-semibold">
                        <button
                          onClick={() => handleDelete(member.trigramme)}
                          className="px-2.5 py-1.5 text-red-600 hover:bg-red-50 rounded-md border border-red-200 transition-all animate-none"
                        >
                          Supprimer
                        </button>
                      </td>
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
