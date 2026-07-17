import api from '../../api/axios'

/* ============================================================================
   API du module Administration (Groupe NTADM) — préfixe `/adminops/`. Reflète
   exactement `apps/adminops/urls.py`. Société posée côté serveur.
   ========================================================================== */

const adminopsApi = {
  healthScore: () => api.get('/adminops/health-score/'),
  adoption: (periode = 30) => api.get('/adminops/adoption/', { params: { periode } }),
  trackerUsage: (module, ecran) =>
    api.post('/adminops/tracker-usage/', { module, ecran }),
  getSettings: () => api.get('/adminops/settings/'),
  updateSettings: (data) => api.patch('/adminops/settings/', data),
  diagnostic: () => api.get('/adminops/diagnostic/'),

  // Sandbox (NTADM12)
  listSandbox: () => api.get('/adminops/sandbox/'),
  creerSandbox: () => api.post('/adminops/sandbox/creer/'),
  prolongerSandbox: (id) => api.post(`/adminops/sandbox/${id}/prolonger/`),

  // Packages de configuration (NTADM15/31)
  listPackages: () => api.get('/adminops/config-packages/'),
  exporterPackage: (nom) => api.post('/adminops/config-packages/exporter/', { nom }),
  previsualiserPackage: (contenu) =>
    api.post('/adminops/config-packages/previsualiser/', { contenu }),
  appliquerPackage: (contenu) =>
    api.post('/adminops/config-packages/appliquer/', { contenu }),
}

export default adminopsApi
