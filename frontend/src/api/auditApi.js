import api from './axios'

// Journal d'activité (Feature G). Réservé aux porteurs de « journal_activite_voir ».
const auditApi = {
  // Statistiques bucketées (Jour=24h, Semaine/Mois=par jour) en Africa/Casablanca.
  getStats: (params) => api.get('/audit/stats/', { params }),
  // Liste paginée filtrable (plus récent d'abord).
  getEntries: (params) => api.get('/audit/entries/', { params }),
  // Données de la barre de filtres (utilisateurs, actions, modules).
  getMeta: () => api.get('/audit/meta/'),
  // YHARD3 — reconstruction champ-par-champ d'un objet à une date passée
  // (rejoue les diffs structurés de AuditLog.changes). `contentType` =
  // "app_label.model" (ex. "crm.client"), `date` optionnelle (ISO), sinon
  // "maintenant". Réservé admin/Directeur (le backend re-vérifie :
  // CanViewActivityLog), scopé société.
  getObjectAsOf: (contentType, objectId, date) =>
    api.get(`/audit/objets/${contentType}/${objectId}/as-of/`, {
      params: date ? { date } : {},
    }),
  // WIR18 — onglet « Sécurité » du Journal (connexion/déconnexion/échec/
  // alerte), FG23, mêmes filtres que le Journal global (user/from/to/search).
  getSecurityEvents: (params) => api.get('/audit/security/', { params }),
  // NTSEC15 — export CSV des évènements de sécurité, gated côté serveur
  // `IsAdminRole` (Directeur/Administrateur) : 403 pour tout autre rôle.
  exportSecurityEvents: (params) =>
    api.get('/audit/security/export/', { params, responseType: 'blob' }),
}

export default auditApi
