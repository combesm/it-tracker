import React, { useState, useEffect, useMemo } from 'react';

export default function Assets({ backendUrl }) {
  const [assets, setAssets] = useState([]);
  const [team, setTeam] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editingAsset, setEditingAsset] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [expandedAssetId, setExpandedAssetId] = useState(null);

  // Form State
  const [nomProduit, setNomProduit] = useState('');
  const [fournisseur, setFournisseur] = useState('');
  const [versionActuelle, setVersionActuelle] = useState('');
  const [typeDeploiement, setTypeDeploiement] = useState('SaaS');
  const [machineHebergement, setMachineHebergement] = useState('');
  const [typeLicence, setTypeLicence] = useState('Perpétuelle');
  const [dateExpiration, setDateExpiration] = useState('');
  const [urls, setUrls] = useState(['']);
  const [tags, setTags] = useState('');
  const [filterTag, setFilterTag] = useState('');
  const [filterMode, setFilterMode] = useState('include'); // 'include' or 'exclude'
  const [responsable, setResponsable] = useState('');
  const [entites, setEntites] = useState(['Groupe']);

  const fetchAssets = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${backendUrl}/api/assets`);
      if (res.ok) {
        const data = await res.json();
        setAssets(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchTeam = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/team`);
      if (res.ok) {
        const data = await res.json();
        setTeam(data);
        if (data.length > 0 && !responsable) {
          setResponsable(data[0].trigramme);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchAssets();
    fetchTeam();
  }, []);

  // Règles de gestion de la licence et du déploiement
  useEffect(() => {
    if (typeLicence === 'Perpétuelle') {
      setDateExpiration('');
    }
  }, [typeLicence]);

  useEffect(() => {
    if (typeDeploiement !== 'Self-hosted') {
      setMachineHebergement('');
    }
  }, [typeDeploiement]);

  const openAddForm = () => {
    setEditingAsset(null);
    setNomProduit('');
    setFournisseur('');
    setVersionActuelle('');
    setTypeDeploiement('SaaS');
    setMachineHebergement('');
    setTypeLicence('Perpétuelle');
    setDateExpiration('');
    setUrls(['']);
    setTags('');
    setEntites(['Groupe']);
    if (team.length > 0) {
      setResponsable(team[0].trigramme);
    } else {
      setResponsable('');
    }
    setErrorMessage('');
    setFormOpen(true);
  };

  const openEditForm = (asset) => {
    setEditingAsset(asset);
    setNomProduit(asset.nom_produit);
    setFournisseur(asset.fournisseur || '');
    setVersionActuelle(asset.version_actuelle);
    setTypeDeploiement(asset.type_deploiement);
    setMachineHebergement(asset.machine_hebergement || '');
    setTypeLicence(asset.type_licence || 'Perpétuelle');
    setDateExpiration(asset.date_expiration || '');
    setUrls(asset.urls && asset.urls.length > 0 ? asset.urls : [asset.url_rss || '']);
    setTags(asset.tags ? (Array.isArray(asset.tags) ? asset.tags.join(', ') : asset.tags) : '');
    setResponsable(asset.responsable);
    setEntites(asset.entites ? asset.entites.split(', ') : ['Groupe']);
    setErrorMessage('');
    setFormOpen(true);
  };

  const handleEntityChange = (option, checked) => {
    if (checked) {
      setEntites([...entites, option]);
    } else {
      setEntites(entites.filter(item => item !== option));
    }
  };

  const toggleExpand = (id) => {
    setExpandedAssetId(prev => prev === id ? null : id);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');

    // Validation : Seuls les champs Nom, version, déploiement et responsable sont requis
    if (!nomProduit.trim() || !versionActuelle.trim() || !typeDeploiement || !responsable) {
      setErrorMessage("Veuillez remplir les champs obligatoires (Nom du produit, Version actuelle, Déploiement et Responsable).");
      return;
    }

    if (typeDeploiement === 'Self-hosted' && !machineHebergement.trim()) {
      setErrorMessage("L'hôte d'hébergement est requis pour un déploiement Self-hosted.");
      return;
    }

    if (typeLicence === 'Limitée' && !dateExpiration) {
      setErrorMessage("La date d'expiration de la licence est requise.");
      return;
    }

    const payload = {
      nom_produit: nomProduit.trim(),
      fournisseur: fournisseur.trim() || null,
      version_actuelle: versionActuelle.trim(),
      type_deploiement: typeDeploiement,
      machine_hebergement: typeDeploiement === 'Self-hosted' ? machineHebergement.trim() : null,
      type_licence: typeLicence,
      date_expiration: typeLicence === 'Limitée' ? dateExpiration : null,
      urls: urls.map(u => u.trim()).filter(Boolean),
      url_rss: urls.map(u => u.trim()).filter(Boolean)[0] || null,
      tags: tags,
      responsable: responsable,
      entites: entites
    };

    try {
      let url = `${backendUrl}/api/assets`;
      let method = 'POST';

      if (editingAsset) {
        url = `${backendUrl}/api/assets/${editingAsset.id}`;
        method = 'PUT';
      }

      const res = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        setFormOpen(false);
        fetchAssets();
      } else {
        const data = await res.json();
        setErrorMessage(data.error || "Une erreur est survenue lors de l'enregistrement.");
      }
    } catch (err) {
      setErrorMessage("Erreur de connexion avec le serveur.");
      console.error(err);
    }
  };

  const handleDelete = async (assetId) => {
    if (!confirm("Voulez-vous supprimer cet actif ? Les alertes associées seront également purgées.")) {
      return;
    }

    try {
      const res = await fetch(`${backendUrl}/api/assets/${assetId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        fetchAssets();
      } else {
        alert("Erreur lors de la suppression de l'actif.");
      }
    } catch (err) {
      console.error(err);
    }
  };

  const allTags = useMemo(() => {
    const tagSet = new Set();
    assets.forEach(asset => {
      if (asset.tags) {
        const tList = Array.isArray(asset.tags) 
          ? asset.tags 
          : asset.tags.split(',').map(t => t.trim()).filter(Boolean);
        tList.forEach(t => tagSet.add(t.toLowerCase().trim()));
      }
    });
    return Array.from(tagSet).sort();
  }, [assets]);

  const filteredAssets = useMemo(() => {
    if (!filterTag) return assets;
    return assets.filter(asset => {
      const tList = (asset.tags || []).map(t => t.toLowerCase().trim());
      const isPresent = tList.includes(filterTag.toLowerCase().trim());
      return filterMode === 'include' ? isPresent : !isPresent;
    });
  }, [assets, filterTag, filterMode]);

  const getTagStyle = (tag) => {
    let hash = 0;
    for (let i = 0; i < tag.length; i++) {
      hash = tag.charCodeAt(i) + ((hash << 5) - hash);
    }
    const colors = [
      { bg: 'bg-blue-50 border-blue-200 text-blue-700', hover: 'hover:bg-blue-100' },
      { bg: 'bg-emerald-50 border-emerald-200 text-emerald-700', hover: 'hover:bg-emerald-100' },
      { bg: 'bg-violet-50 border-violet-200 text-violet-700', hover: 'hover:bg-violet-100' },
      { bg: 'bg-amber-50 border-amber-200 text-amber-700', hover: 'hover:bg-amber-100' },
      { bg: 'bg-rose-50 border-rose-200 text-rose-700', hover: 'hover:bg-rose-100' },
      { bg: 'bg-cyan-50 border-cyan-200 text-cyan-700', hover: 'hover:bg-cyan-100' }
    ];
    return colors[Math.abs(hash) % colors.length];
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-brand-dark">Actifs & Services</h1>
          <p className="text-sm text-brand-text/70 mt-1">
            Inventaire des logiciels, services et systèmes exploités par la PME.
          </p>
        </div>
        {!formOpen && (
          <button
            onClick={openAddForm}
            className="mt-4 md:mt-0 px-4 py-2 bg-brand-primary text-white text-sm font-semibold rounded-lg hover:bg-brand-primary/95 transition-all shadow-sm flex items-center self-start"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
            </svg>
            Ajouter un actif
          </button>
        )}
      </div>

      {/* Form Card */}
      {formOpen && (
        <div className="bg-brand-card rounded-lg border border-brand-border shadow-sm p-6 transition-all duration-300">
          <div className="flex items-center justify-between border-b border-brand-border pb-4 mb-6">
            <h3 className="text-lg font-bold text-brand-dark">
              {editingAsset ? "Modifier l'actif" : "Ajouter un nouvel actif"}
            </h3>
            <button
              onClick={() => setFormOpen(false)}
              className="text-brand-text/50 hover:text-brand-text p-1.5 hover:bg-brand-bg rounded-lg transition-all"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>

          {errorMessage && (
            <div className="p-3 bg-brand-alertBg text-brand-alert rounded-lg text-xs font-semibold border border-brand-alert/20 mb-6">
              {errorMessage}
            </div>
          )}

          {team.length === 0 ? (
            <div className="p-4 bg-brand-alertBg text-brand-alert rounded-lg text-sm border border-brand-alert/20 text-center font-medium">
              Veuillez d'abord enregistrer un membre de l'équipe pour pouvoir désigner un responsable.
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Nom du produit */}
                <div>
                  <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">Nom du produit *</label>
                  <input
                    type="text"
                    required
                    value={nomProduit}
                    onChange={(e) => setNomProduit(e.target.value)}
                    className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary"
                  />
                </div>

                {/* Fournisseur */}
                <div>
                  <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">Fournisseur</label>
                  <input
                    type="text"
                    value={fournisseur}
                    onChange={(e) => setFournisseur(e.target.value)}
                    className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary"
                  />
                </div>

                {/* Version actuelle */}
                <div>
                  <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">Version actuelle *</label>
                  <input
                    type="text"
                    required
                    value={versionActuelle}
                    onChange={(e) => setVersionActuelle(e.target.value)}
                    className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary"
                  />
                </div>

                {/* Responsable */}
                <div>
                  <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">Responsable *</label>
                  <select
                    value={responsable}
                    onChange={(e) => setResponsable(e.target.value)}
                    className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg bg-white focus:outline-none focus:border-brand-primary"
                  >
                    {team.map((member) => (
                      <option key={member.trigramme} value={member.trigramme}>
                        {member.trigramme} ({member.email})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Type de déploiement */}
                <div>
                  <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">Type de déploiement *</label>
                  <select
                    value={typeDeploiement}
                    onChange={(e) => setTypeDeploiement(e.target.value)}
                    className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg bg-white focus:outline-none focus:border-brand-primary"
                  >
                    <option value="SaaS">SaaS</option>
                    <option value="Self-hosted">Self-hosted</option>
                    <option value="On-premise">On-premise</option>
                  </select>
                </div>

                {/* Type de licence */}
                <div>
                  <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">Type de licence</label>
                  <select
                    value={typeLicence}
                    onChange={(e) => setTypeLicence(e.target.value)}
                    className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg bg-white focus:outline-none focus:border-brand-primary"
                  >
                    <option value="Perpétuelle">Perpétuelle</option>
                    <option value="Limitée">Limitée</option>
                  </select>
                </div>

                {/* Multi-selection Entités */}
                <div className="col-span-1 md:col-span-2">
                  <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">Entité(s) associée(s)</label>
                  <div className="flex flex-wrap gap-5 py-2">
                    {['Groupe', 'Herakles', 'Oztyis', 'Hexatio'].map((option) => (
                      <label key={option} className="inline-flex items-center text-sm font-semibold text-brand-text cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={entites.includes(option)}
                          onChange={(e) => handleEntityChange(option, e.target.checked)}
                          className="rounded border-brand-border text-brand-primary focus:ring-brand-primary h-4 w-4 mr-2"
                        />
                        {option}
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              {/* Dynamic Fields with transitions */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Hosting */}
                <div 
                  className={`overflow-hidden transition-all duration-300 ease-in-out ${
                    typeDeploiement === 'Self-hosted' 
                      ? 'max-h-24 opacity-100' 
                      : 'max-h-0 opacity-0 pointer-events-none'
                  }`}
                >
                  <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">
                    Machine / Serveur d'hébergement *
                  </label>
                  <input
                    type="text"
                    required={typeDeploiement === 'Self-hosted'}
                    value={machineHebergement}
                    onChange={(e) => setMachineHebergement(e.target.value)}
                    className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary"
                  />
                </div>

                {/* Expiration date */}
                <div 
                  className={`overflow-hidden transition-all duration-300 ease-in-out ${
                    typeLicence === 'Limitée' 
                      ? 'max-h-24 opacity-100' 
                      : 'max-h-0 opacity-0 pointer-events-none'
                  }`}
                >
                  <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">
                    Date d'expiration de la licence *
                  </label>
                  <input
                    type="date"
                    required={typeLicence === 'Limitée'}
                    value={dateExpiration}
                    onChange={(e) => setDateExpiration(e.target.value)}
                    className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary"
                  />
                </div>
              </div>

              {/* URLs Flux RSS / XML Joomla (Multi-sources) */}
              <div className="space-y-3">
                <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider">
                  Sources de flux (RSS, XML Joomla ou OpenCVE Interne)
                </label>
                <div className="space-y-3">
                  {urls.map((url, index) => {
                    const parsed = (() => {
                      if (url.startsWith('opencve://')) {
                        const p = url.substring(10).split('/');
                        if (p[0] === 'product') {
                          return { type: 'opencve', subType: 'product', vendor: p[1] || '', product: p[2] || '' };
                        } else {
                          return { type: 'opencve', subType: 'vendor', vendor: p[1] || '', product: '' };
                        }
                      }
                      return { type: 'standard', subType: '', vendor: '', product: '' };
                    })();

                    const handleTypeChange = (newType) => {
                      const newUrls = [...urls];
                      if (newType === 'opencve') {
                        newUrls[index] = 'opencve://product//';
                      } else {
                        newUrls[index] = '';
                      }
                      setUrls(newUrls);
                    };

                    const handleSubTypeChange = (newSubType) => {
                      const newUrls = [...urls];
                      if (newSubType === 'product') {
                        newUrls[index] = `opencve://product/${parsed.vendor}/`;
                      } else {
                        newUrls[index] = `opencve://vendor/${parsed.vendor}`;
                      }
                      setUrls(newUrls);
                    };

                    const handleOpenCveChange = (vendor, product) => {
                      const newUrls = [...urls];
                      if (parsed.subType === 'product') {
                        newUrls[index] = `opencve://product/${vendor.trim()}/${product.trim()}`;
                      } else {
                        newUrls[index] = `opencve://vendor/${vendor.trim()}`;
                      }
                      setUrls(newUrls);
                    };

                    return (
                      <div key={index} className="p-3.5 bg-brand-bg/10 border border-brand-border/60 rounded-xl space-y-3 shadow-xs">
                        <div className="flex items-center justify-between gap-3">
                          {/* Sélecteur de type */}
                          <div className="flex gap-1 bg-brand-bg/40 p-0.5 rounded-lg border border-brand-border/50">
                            <button
                              type="button"
                              onClick={() => handleTypeChange('standard')}
                              className={`px-3 py-1 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                                parsed.type === 'standard'
                                  ? 'bg-white text-brand-primary shadow-xs'
                                  : 'text-brand-dark/60 hover:text-brand-dark'
                              }`}
                            >
                              🔗 Flux RSS/XML
                            </button>
                            <button
                              type="button"
                              onClick={() => handleTypeChange('opencve')}
                              className={`px-3 py-1 text-[11px] font-bold rounded-md transition-all cursor-pointer ${
                                parsed.type === 'opencve'
                                  ? 'bg-white text-brand-primary shadow-xs'
                                  : 'text-brand-dark/60 hover:text-brand-dark'
                              }`}
                            >
                              🛡️ OpenCVE Interne
                            </button>
                          </div>

                          {/* Bouton de suppression */}
                          {urls.length > 1 && (
                            <button
                              type="button"
                              onClick={() => {
                                setUrls(urls.filter((_, i) => i !== index));
                              }}
                              className="p-1.5 text-brand-alert hover:bg-brand-alert/10 rounded-lg border border-transparent hover:border-brand-alert/20 transition-all cursor-pointer"
                              title="Supprimer cette source"
                            >
                              <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          )}
                        </div>

                        {/* Champs dynamiques selon le type */}
                        {parsed.type === 'standard' ? (
                          <input
                            type="text"
                            placeholder="https://exemple.com/feed.xml"
                            value={url}
                            onChange={(e) => {
                              const newUrls = [...urls];
                              newUrls[index] = e.target.value;
                              setUrls(newUrls);
                            }}
                            className="w-full px-3 py-2 text-sm border border-brand-border bg-white rounded-lg focus:outline-none focus:border-brand-primary"
                          />
                        ) : (
                          <div className="space-y-3 pt-1">
                            {/* Sélecteur de sous-type OpenCVE */}
                            <div className="flex gap-2 items-center">
                              <span className="text-[10px] font-bold text-brand-dark/50 uppercase tracking-wider">Filtrer par :</span>
                              <button
                                type="button"
                                onClick={() => handleSubTypeChange('product')}
                                className={`px-2 py-0.5 text-[10px] font-bold rounded-md border transition-all cursor-pointer ${
                                  parsed.subType === 'product'
                                    ? 'bg-brand-dark text-white border-brand-dark shadow-xs'
                                    : 'bg-white text-brand-dark/70 border-brand-border hover:bg-brand-bg/40'
                                }`}
                              >
                                Produit (Recommandé)
                              </button>
                              <button
                                type="button"
                                onClick={() => handleSubTypeChange('vendor')}
                                className={`px-2 py-0.5 text-[10px] font-bold rounded-md border transition-all cursor-pointer ${
                                  parsed.subType === 'vendor'
                                    ? 'bg-brand-dark text-white border-brand-dark shadow-xs'
                                    : 'bg-white text-brand-dark/70 border-brand-border hover:bg-brand-bg/40'
                                }`}
                              >
                                Éditeur uniquement
                              </button>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <label className="block text-[9px] font-bold text-brand-dark/60 uppercase tracking-wider mb-1">Éditeur (ex: joomla)</label>
                                <input
                                  type="text"
                                  placeholder="ex: rustdesk"
                                  value={parsed.vendor}
                                  onChange={(e) => handleOpenCveChange(e.target.value, parsed.product)}
                                  className="w-full px-3 py-2 text-xs border border-brand-border bg-white rounded-lg focus:outline-none focus:border-brand-primary"
                                />
                              </div>
                              {parsed.subType === 'product' && (
                                <div>
                                  <label className="block text-[9px] font-bold text-brand-dark/60 uppercase tracking-wider mb-1">Produit (ex: joomla_cve)</label>
                                  <input
                                    type="text"
                                    placeholder="ex: rustdesk"
                                    value={parsed.product}
                                    onChange={(e) => handleOpenCveChange(parsed.vendor, e.target.value)}
                                    className="w-full px-3 py-2 text-xs border border-brand-border bg-white rounded-lg focus:outline-none focus:border-brand-primary"
                                  />
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                <button
                  type="button"
                  onClick={() => setUrls([...urls, ''])}
                  className="mt-1 px-3 py-1.5 text-xs font-semibold text-brand-primary hover:bg-brand-primary/10 rounded-lg border border-transparent hover:border-brand-primary/20 transition-all flex items-center gap-1 cursor-pointer"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                  </svg>
                  Ajouter une source
                </button>
              </div>

              {/* Étiquettes / Tags */}
              <div>
                <label className="block text-xs font-bold text-brand-dark uppercase tracking-wider mb-2">
                  Étiquettes (tags, séparés par des virgules)
                </label>
                <input
                  type="text"
                  list="available-tags"
                  placeholder="ex: joomla, extension, critique"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="w-full px-4 py-2 text-sm border border-brand-border rounded-lg focus:outline-none focus:border-brand-primary"
                />
                <datalist id="available-tags">
                  {allTags.map((t, idx) => (
                    <option key={idx} value={t} />
                  ))}
                </datalist>
                
                {/* Clickable available tags suggestion list */}
                {allTags.length > 0 && (
                  <div className="mt-2">
                    <span className="text-[10px] font-bold text-brand-dark/50 uppercase tracking-wider block mb-1">
                      Étiquettes existantes (cliquer pour ajouter) :
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {allTags.map((t, idx) => {
                        const currentTagsList = tags.split(',').map(item => item.trim().toLowerCase());
                        if (currentTagsList.includes(t.toLowerCase().trim())) return null;
                        
                        return (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => {
                              const trimmed = tags.trim();
                              if (trimmed === '') {
                                setTags(t);
                              } else if (trimmed.endsWith(',')) {
                                setTags(`${trimmed} ${t}`);
                              } else {
                                setTags(`${trimmed}, ${t}`);
                              }
                            }}
                            className="px-2 py-0.5 rounded text-[10px] font-semibold bg-brand-bg text-brand-dark border border-brand-border/60 hover:bg-brand-primary/10 hover:text-brand-primary hover:border-brand-primary/20 transition-all cursor-pointer"
                          >
                            + {t}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* Form Buttons */}
              <div className="flex items-center justify-end space-x-4 border-t border-brand-border pt-4">
                <button
                  type="button"
                  onClick={() => setFormOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-brand-text/75 hover:bg-brand-bg rounded-lg transition-all"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-brand-primary text-white text-xs font-semibold rounded-lg hover:bg-brand-primary/95 transition-all shadow-sm"
                >
                  {editingAsset ? "Enregistrer" : "Créer l'actif"}
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Tag Filter Bar */}
      {!formOpen && allTags.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 bg-brand-card p-4 rounded-lg border border-brand-border shadow-sm animate-fadeIn">
          <span className="text-xs font-bold text-brand-dark/60 uppercase tracking-wider mr-2">Filtrer par étiquette :</span>
          <button
            onClick={() => {
              setFilterTag('');
              setFilterMode('include');
            }}
            className={`px-3 py-1 text-xs font-semibold rounded-full border transition-all cursor-pointer ${
              !filterTag
                ? 'bg-brand-primary text-white border-brand-primary shadow-sm'
                : 'bg-brand-bg text-brand-text/80 border-brand-border hover:bg-brand-bg/85'
            }`}
          >
            Tous
          </button>
          {allTags.map((tag, idx) => {
            const isSelected = filterTag === tag;
            const style = getTagStyle(tag);
            
            const handleClick = () => {
              if (filterTag === tag) {
                if (filterMode === 'include') {
                  setFilterMode('exclude');
                } else {
                  setFilterTag('');
                  setFilterMode('include');
                }
              } else {
                setFilterTag(tag);
                setFilterMode('include');
              }
            };
            
            let btnClass = `px-3 py-1 text-xs font-bold rounded-full border transition-all cursor-pointer flex items-center gap-1 `;
            if (isSelected) {
              if (filterMode === 'include') {
                btnClass += `${style.bg} border-brand-primary shadow-sm ring-1 ring-brand-primary/20`;
              } else {
                btnClass += `bg-brand-bg/60 text-brand-text/35 border-brand-border/65 line-through opacity-70 hover:bg-brand-bg/80`;
              }
            } else {
              btnClass += `bg-white text-brand-text border-brand-border ${style.hover}`;
            }
            
            return (
              <button
                key={idx}
                onClick={handleClick}
                className={btnClass}
                title={isSelected && filterMode === 'exclude' ? "Sauf cette étiquette (cliquer pour effacer le filtre)" : isSelected ? "Cette étiquette uniquement (cliquer pour l'exclure)" : "Filtrer par cette étiquette"}
              >
                {isSelected && filterMode === 'exclude' && (
                  <span className="text-[10px] font-extrabold text-brand-alert/80 mr-0.5">✕</span>
                )}
                {tag}
              </button>
            );
          })}
        </div>
      )}

      {/* Assets Table */}
      <div className="bg-brand-card rounded-lg border border-brand-border shadow-sm">
        <div className="p-6">
          {loading ? (
            <div className="space-y-4 py-4">
              <div className="h-6 bg-brand-bg animate-pulse rounded w-full"></div>
              <div className="h-6 bg-brand-bg animate-pulse rounded w-11/12"></div>
            </div>
          ) : assets.length === 0 ? (
            <div className="text-center py-12">
              <span className="text-sm text-brand-text/50 font-medium block">
                Aucun actif enregistré.
              </span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-brand-border">
                <thead>
                  <tr className="bg-brand-bg/50">
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Produit</th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Version</th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Responsable</th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold text-brand-dark uppercase tracking-wider">Licence</th>
                    <th scope="col" className="relative px-4 py-3 text-right">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-brand-border">
                  {filteredAssets.map((asset) => {
                    const isExpanded = expandedAssetId === asset.id;
                    return (
                      <React.Fragment key={asset.id}>
                        {/* Main row */}
                        <tr 
                          onClick={() => toggleExpand(asset.id)}
                          className={`hover:bg-brand-bg/20 cursor-pointer transition-colors ${
                            isExpanded ? 'bg-brand-bg/10' : ''
                          }`}
                        >
                          {/* Produit (with rotate chevron) */}
                          <td className="px-4 py-4 whitespace-nowrap text-sm font-bold text-brand-dark">
                            <div className="flex items-center">
                              <svg 
                                className={`w-4 h-4 mr-2.5 text-brand-text/50 transition-transform duration-200 ${
                                  isExpanded ? 'rotate-90' : ''
                                }`} 
                                fill="none" 
                                stroke="currentColor" 
                                viewBox="0 0 24 24" 
                                xmlns="http://www.w3.org/2000/svg"
                              >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 5l7 7-7 7"></path>
                              </svg>
                              <div className="flex flex-col py-0.5">
                                <span className="font-bold text-brand-dark">{asset.nom_produit}</span>
                                {asset.tags && asset.tags.length > 0 && (
                                  <div className="flex flex-wrap gap-1 mt-1">
                                    {asset.tags.map((tag, tIdx) => {
                                      const style = getTagStyle(tag);
                                      return (
                                        <span 
                                          key={tIdx} 
                                          className={`px-1.5 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-wider border ${style.bg}`}
                                        >
                                          {tag}
                                        </span>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                          {/* Version */}
                          <td className="px-4 py-4 whitespace-nowrap text-xs font-semibold text-brand-text/80">
                            {asset.version_actuelle}
                          </td>
                          {/* Responsable */}
                          <td className="px-4 py-4 whitespace-nowrap text-xs font-bold">
                            <span className="px-2.5 py-1 bg-brand-bg text-brand-dark border border-brand-border rounded" title={asset.email_responsable}>
                              {asset.responsable}
                            </span>
                          </td>
                          {/* Licence */}
                          <td className="px-4 py-4 whitespace-nowrap text-xs font-semibold">
                            <span className={`inline-flex px-2 py-0.5 rounded-full ${
                              asset.type_licence === 'Limitée'
                                ? 'bg-brand-alert/10 text-brand-alert'
                                : 'bg-brand-successBg text-brand-success'
                            }`}>
                              {asset.type_licence || 'Perpétuelle'}
                            </span>
                          </td>
                          {/* Actions (stop propagation to avoid toggling collapse) */}
                          <td className="px-4 py-4 whitespace-nowrap text-right text-xs font-semibold space-x-2" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => openEditForm(asset)}
                              className="px-2.5 py-1.5 text-brand-primary hover:bg-brand-primary/10 rounded-md border border-brand-primary/20 transition-all"
                            >
                              Modifier
                            </button>
                            <button
                              onClick={() => handleDelete(asset.id)}
                              className="px-2.5 py-1.5 text-red-600 hover:bg-red-50 rounded-md border border-red-200 transition-all"
                            >
                              Supprimer
                            </button>
                          </td>
                        </tr>

                        {/* Collapsible details panel */}
                        {isExpanded && (
                          <tr className="bg-brand-bg/5">
                            <td colSpan={5} className="px-8 py-4 border-t border-b border-brand-border/60">
                              <div className="bg-white rounded-lg border border-brand-border/60 p-5 shadow-sm grid grid-cols-1 md:grid-cols-3 gap-6">
                                {/* Entités associated */}
                                <div>
                                  <span className="block text-[10px] font-bold text-brand-dark/60 uppercase tracking-wider">Entités associées</span>
                                  <div className="flex flex-wrap gap-1 mt-1.5">
                                    {(asset.entites || 'Groupe').split(', ').map((ent, idx) => (
                                      <span key={idx} className="inline-flex px-2 py-0.5 rounded bg-brand-bg text-brand-dark border border-brand-border/60 font-semibold text-[10px]">
                                        {ent}
                                      </span>
                                    ))}
                                  </div>
                                </div>

                                {/* Fournisseur */}
                                <div>
                                  <span className="block text-[10px] font-bold text-brand-dark/60 uppercase tracking-wider">Fournisseur</span>
                                  <span className="font-semibold text-brand-text text-sm mt-1.5 block">
                                    {asset.fournisseur || 'Non spécifié'}
                                  </span>
                                </div>

                                {/* Déploiement */}
                                <div>
                                  <span className="block text-[10px] font-bold text-brand-dark/60 uppercase tracking-wider">Type de déploiement</span>
                                  <span className="font-semibold text-brand-text text-sm mt-1.5 block">
                                    {asset.type_deploiement}
                                  </span>
                                </div>

                                {/* Machine/Serveur - Self-hosted */}
                                {asset.type_deploiement === 'Self-hosted' && (
                                  <div>
                                    <span className="block text-[10px] font-bold text-brand-dark/60 uppercase tracking-wider">Machine / Serveur d'hébergement</span>
                                    <span className="font-semibold text-brand-text text-sm mt-1.5 block italic text-brand-primary">
                                      {asset.machine_hebergement || '-'}
                                    </span>
                                  </div>
                                )}

                                {/* Date d'expiration - Limitée */}
                                {asset.type_licence === 'Limitée' && (
                                  <div>
                                    <span className="block text-[10px] font-bold text-brand-dark/60 uppercase tracking-wider">Date d'expiration de licence</span>
                                    <span className="font-semibold text-brand-text text-sm mt-1.5 block">
                                      {asset.date_expiration ? new Date(asset.date_expiration).toLocaleDateString('fr-FR') : '-'}
                                    </span>
                                  </div>
                                )}

                                {/* URL RSS */}
                                <div>
                                  <span className="block text-[10px] font-bold text-brand-dark/60 uppercase tracking-wider">Sources de flux ({asset.urls?.length || 0})</span>
                                  <div className="mt-1.5 space-y-1">
                                    {asset.urls && asset.urls.length > 0 ? (
                                      asset.urls.map((url, uidx) => (
                                        <span key={uidx} className="font-medium text-brand-text text-sm block truncate" title={url}>
                                          <a href={url} target="_blank" rel="noopener noreferrer" className="text-brand-primary hover:underline">
                                            {url}
                                          </a>
                                        </span>
                                      ))
                                    ) : (
                                      <span className="text-brand-text/45 text-sm block">Aucun flux configuré</span>
                                    )}
                                  </div>
                                </div>
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
    </div>
  );
}
