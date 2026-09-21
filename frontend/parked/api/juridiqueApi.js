import api from './axios'

/* ============================================================================
   Affaires juridiques (apps/juridique, groupe NTJUR) — client API.
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /juridique/... ».
   Un seul point d'import pour tous les écrans du module.

   Contrats serveur à NE PAS ré-inventer côté écran :
   * ``statut`` d'un dossier est en LECTURE SEULE — il n'avance que par
     ``changer-statut`` / ``clore`` (machine à états gardée côté serveur) ;
   * ``proposer-provision`` et ``reprendre-provision`` suivent le patron
     « propose → confirme » : SANS ``confirme: true``, le serveur ne poste
     AUCUNE écriture comptable et renvoie 400 avec un aperçu ;
   * les dossiers ``confidentiel`` sont filtrés CÔTÉ SERVEUR (absents de la
     liste, 404 en détail) — l'écran n'a aucun filtrage à refaire.
   ========================================================================== */

const juridiqueApi = {
  // ── Dossiers ──
  list: (params) => api.get('/juridique/dossiers/', { params }),
  get: (id) => api.get(`/juridique/dossiers/${id}/`),
  create: (data) => api.post('/juridique/dossiers/', data),
  update: (id, data) => api.patch(`/juridique/dossiers/${id}/`, data),
  remove: (id) => api.delete(`/juridique/dossiers/${id}/`),

  // ── Cockpit & agrégats (lecture seule) ──
  tableauBord: () => api.get('/juridique/dossiers/tableau-bord/'),
  budget: (id) => api.get(`/juridique/dossiers/${id}/budget/`),
  timeline: (id) => api.get(`/juridique/dossiers/${id}/timeline/`),

  // ── Machine à états (statut posé côté serveur) ──
  statutsSuivants: (id) =>
    api.get(`/juridique/dossiers/${id}/statuts-suivants/`),
  changerStatut: (id, statut, motif) =>
    api.post(`/juridique/dossiers/${id}/changer-statut/`, { statut, motif }),
  clore: (id, statutFinal, motif) =>
    api.post(`/juridique/dossiers/${id}/clore/`,
      { statut_final: statutFinal, motif }),

  // ── Provisions (« propose → confirme », jamais automatique) ──
  proposerProvision: (id, data) =>
    api.post(`/juridique/dossiers/${id}/proposer-provision/`, data),
  reprendreProvision: (id, data) =>
    api.post(`/juridique/dossiers/${id}/reprendre-provision/`, data),

  // ── Workflow d'approbation d'un engagement ──
  etapesApprobation: (id) =>
    api.get(`/juridique/dossiers/${id}/etapes-approbation/`),
  lancerApprobationMandat: (id, data) =>
    api.post(`/juridique/dossiers/${id}/lancer-approbation-mandat/`, data),
  approuverEtape: (id, data) =>
    api.post(`/juridique/dossiers/${id}/approuver-etape/`, data),
  rejeterEtape: (id, data) =>
    api.post(`/juridique/dossiers/${id}/rejeter-etape/`, data),

  // ── Conseils externes & honoraires ──
  cabinets: (params) => api.get('/juridique/cabinets-avocats/', { params }),
  mandats: (params) => api.get('/juridique/mandats/', { params }),
  activerMandat: (id) => api.post(`/juridique/mandats/${id}/activer/`),
  notesHonoraires: (params) =>
    api.get('/juridique/notes-honoraires/', { params }),

  // ── Échéancier procédural ──
  audiences: (params) => api.get('/juridique/audiences/', { params }),
  delaisPrescription: (params) =>
    api.get('/juridique/delais-prescription/', { params }),
}

export default juridiqueApi
