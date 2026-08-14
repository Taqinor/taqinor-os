import api from './axios'
import { makeResourceFactory, unwrapList } from './resource'
import { downloadBlobInGesture } from '../utils/downloadBlob'

/* ============================================================================
   NTMKT1 — Client API du module « Marketing » (apps/marketing).
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /marketing/... »
   (préfixe ODX10, `apps/marketing/urls.py`). PACT26 — l'ancien préfixe
   historique `/compta/...` qui servait les MÊMES ViewSets a été retiré
   (double montage) ; `CampagnesScreen.jsx` a été migré ici. Un seul
   point d'import pour tous les écrans marketing NTMKT1-11+. Aucune donnée
   sensible (`Produit.prix_achat`/marge) n'est demandée ni rendue nulle part
   dans ce module.
   ========================================================================== */

const resource = makeResourceFactory(api, '/marketing')

export function downloadBlob(blob, filename) {
  downloadBlobInGesture().deliver(blob instanceof Blob ? blob : new Blob([blob]), filename)
}

const marketingApi = {
  unwrapList,
  downloadBlob,

  // ── NTMKT2/3 — Campagnes + trace d'envoi par destinataire (XMKT2) ──
  campagnes: {
    ...resource('campagnes'),
    envoyer: (id, data) => api.post(`/marketing/campagnes/${id}/envoyer/`, data),
    envoyerTest: (id, data) =>
      api.post(`/marketing/campagnes/${id}/envoyer-test/`, data),
    precheck: (id, params) =>
      api.get(`/marketing/campagnes/${id}/precheck/`, { params }),
    apercuFusion: (id, params) =>
      api.get(`/marketing/campagnes/${id}/apercu_fusion/`, { params }),
    roi: (id) => api.get(`/marketing/campagnes/${id}/roi/`),
    clicsParLien: (id) => api.get(`/marketing/campagnes/${id}/clics-par-lien/`),
    // XMKT34 — sonde de gating (aucun appel LLM) + génération SUGGESTION
    // éditable (jamais auto-appliquée). Migré depuis comptaApi (PACT26).
    genererIaDisponible: () =>
      api.get('/marketing/campagnes/generer-ia-disponible/'),
    genererIa: (payload) =>
      api.post('/marketing/campagnes/generer-ia/', payload),
  },
  envoisCampagne: {
    list: (params) => api.get('/marketing/envois-campagne/', { params }),
  },
  approbationsEnvoiCampagne: {
    ...resource('approbations-envoi-campagne'),
    approuver: (id) =>
      api.post(`/marketing/approbations-envoi-campagne/${id}/approuver/`),
    rejeter: (id, data) =>
      api.post(`/marketing/approbations-envoi-campagne/${id}/rejeter/`, data),
  },

  // ── NTMKT4 — Segments dynamiques (XMKT6) ──
  segments: {
    ...resource('segments-marketing'),
    previsualiser: (id) =>
      api.get(`/marketing/segments-marketing/${id}/previsualiser/`),
  },

  // ── NTMKT5 — Listes de diffusion + abonnements (XMKT5) ──
  listes: {
    ...resource('listes-diffusion'),
    importer: (id, lignes) =>
      api.post(`/marketing/listes-diffusion/${id}/importer/`, { lignes }),
    abonnes: (id, params) =>
      api.get(`/marketing/listes-diffusion/${id}/abonnes/`, { params }),
  },
  abonnementsListe: resource('abonnements-liste'),

  // ── NTMKT6 — Séquences de relance (FG202/XMKT1/18/19/20) ──
  sequences: {
    ...resource('sequences-relance'),
    planifier: (id) => api.get(`/marketing/sequences-relance/${id}/planifier/`),
    traces: (id, params) =>
      api.get(`/marketing/sequences-relance/${id}/traces/`, { params }),
    compteursParEtape: (id) =>
      api.get(`/marketing/sequences-relance/${id}/compteurs-par-etape/`),
    participants: (id, params) =>
      api.get(`/marketing/sequences-relance/${id}/participants/`, { params }),
  },
  etapesSequence: resource('etapes-sequence'),

  // ── NTMKT12/13 — Journey en graphe (nœuds + arcs) d'une séquence ──
  // Extension ADDITIVE : une séquence sans nœud reste linéaire côté serveur.
  noeudsJourney: resource('noeuds-journey'),
  arcsJourney: resource('arcs-journey'),

  // ── NTMKT24 — Heatmap d'engagement jour x heure (lecture seule) ──
  heatmapEngagement: (params) =>
    api.get('/marketing/heatmap-engagement/', { params }),

  // ── NTMKT23 — Blocs de contenu réutilisables (insérés par COPIE) ──
  blocsContenu: resource('blocs-contenu'),

  // ── NTMKT16 — Versions éditoriales d'une landing page d'intake ──
  versionsFormulaireIntake: {
    ...resource('versions-formulaire-intake'),
    // « Publier cette version » : la page publique bascule dessus.
    publier: (id) =>
      api.post(`/marketing/versions-formulaire-intake/${id}/publier/`),
  },

  // ── NTMKT15 — Bibliothèque de modèles de journeys (graphes pré-construits)
  modelesJourney: {
    ...resource('modeles-journey'),
    // « Utiliser ce modèle » : crée une séquence ÉDITABLE désactivée.
    instancier: (id, data) =>
      api.post(`/marketing/modeles-journey/${id}/instancier/`, data || {}),
  },

  inscriptionsSequence: {
    ...resource('inscriptions-sequence'),
    inscrire: (data) =>
      api.post('/marketing/inscriptions-sequence/inscrire/', data),
  },

  // ── NTMKT7 — Événements marketing (XMKT28, ZMKT14-19) ──
  evenements: {
    ...resource('evenements-marketing'),
    avancerEtape: (id, etape) =>
      api.post(`/marketing/evenements-marketing/${id}/avancer-etape/`, { etape }),
    cloturerPresences: (id) =>
      api.post(`/marketing/evenements-marketing/${id}/cloturer-presences/`),
    borne: (id, q) =>
      api.get(`/marketing/evenements-marketing/${id}/borne/`, { params: { q } }),
  },
  billetsEvenement: resource('billets-evenement'),
  // WIR162 — ZMKT14/16/17 : ces 3 ressources étaient routées côté backend
  // (ViewSets + serializers complets) mais aucun wrapper n'existait côté
  // front, contrairement à `billetsEvenement` (déjà enveloppée, mais elle
  // aussi jamais appelée) — un événement ne se créait qu'avec nom/dates.
  typesEvenement: {
    ...resource('types-evenement'),
    // ZMKT14 — crée un événement à partir d'un modèle réutilisable (recopie
    // `config_defaut`) ; seuls `nom`/`date_debut` restent à saisir.
    creerEvenement: (id, data) =>
      api.post(`/marketing/types-evenement/${id}/creer-evenement/`, data),
  },
  questionsEvenement: resource('questions-evenement'),
  communicationsEvenement: resource('communications-evenement'),
  inscriptionsEvenement: {
    ...resource('inscriptions-evenement'),
    pointer: (id) => api.post(`/marketing/inscriptions-evenement/${id}/pointer/`),
    badgePdf: (id) =>
      api.get(`/marketing/inscriptions-evenement/${id}/badge/`,
        { responseType: 'blob' }),
  },

  // ── NTMKT8 — Enquêtes configurables (XMKT27) ──
  enquetes: {
    ...resource('enquetes'),
    resultats: (id) => api.get(`/marketing/enquetes/${id}/resultats/`),
    tester: (id) => api.get(`/marketing/enquetes/${id}/tester/`),
    resultatsExport: (id) =>
      api.get(`/marketing/enquetes/${id}/resultats/export/`,
        { responseType: 'blob' }),
    // PACT109 — ZMKT13 : liste des soumissions individuelles (filtrable
    // réussi/échoué) — l'écran de résultats n'affichait que l'agrégat.
    participations: (id, params) =>
      api.get(`/marketing/enquetes/${id}/participations/`, { params }),
  },
  // PACT109 — ZMKT10 : certificat PDF d'UNE soumission (route isolée,
  // publique/AllowAny côté serveur — 404 si non certifiée/échouée, aucune
  // fuite d'existence). Téléchargé tel quel, jamais généré côté client.
  reponsesEnquete: {
    certificatUrl: (reponseId) =>
      `/api/django/marketing/reponses-enquete/${reponseId}/certificat/`,
  },

  // ── NTMKT9 — Fidélité (points/mouvements) + règles d'upsell (FG240/241) ──
  comptesFidelite: {
    ...resource('comptes-fidelite'),
    crediter: (id, data) =>
      api.post(`/marketing/comptes-fidelite/${id}/crediter/`, data),
  },
  mouvementsFidelite: resource('mouvements-fidelite'),
  reglesUpsell: resource('regles-upsell'),

  // ── NTMKT10 — Domaine d'envoi (SPF/DKIM/DMARC, XMKT33) + supports offline
  // (QR flyers, XMKT29) ──
  domainesEnvoi: {
    ...resource('domaines-envoi'),
    verifier: (id) => api.post(`/marketing/domaines-envoi/${id}/verifier/`),
    enregistrementsAttendus: (id) =>
      api.get(`/marketing/domaines-envoi/${id}/enregistrements-attendus/`),
  },
  supportsOffline: {
    ...resource('supports-offline'),
    qrUrl: (id) => `/api/django/marketing/supports-offline/${id}/qr/`,
    qr: (id) => api.get(`/marketing/supports-offline/${id}/qr/`,
      { responseType: 'blob' }),
    scansParSupport: () =>
      api.get('/marketing/supports-offline/scans-par-support/'),
  },

  // ── WIR64/FG206 — Formulaires d'intake (landing publique de capture de
  // lead). CRUD admin authentifié ; la soumission publique passe par la vue
  // AllowAny /marketing/intake/<slug>/soumettre/ (jamais ce client). ──
  formulairesIntake: {
    ...resource('formulaires-intake'),
    // URL publique de la landing (partageable), pour information dans l'admin.
    lienPublic: (slug) => `/api/django/marketing/intake/${slug}/`,
  },
  // ── WIR161 — Journal d'appels commercial / click-to-call log (FG208) ──
  // `company`/`auteur` posés côté serveur (jamais lus du corps de requête).
  appels: resource('appels'),

  // ── WIR96 — Suivi d'ouverture des liens de partage + relances de devis
  // abandonné (FG203/FG205). Les deux ressources étaient routées mais sans
  // aucun wrapper côté client. L'ÉCRITURE est faite par `apps/ventes` au
  // moment réel de l'ouverture / de la relance ; ces wrappers sont en
  // LECTURE (listes marketing transverses). La fiche devis, elle, lit le
  // suivi d'UN devis via `ventesApi.getSuiviPartageDevis`. ──
  ouverturesPartage: {
    list: (params) => api.get('/marketing/ouvertures-partage/', { params }),
  },
  relancesDevisAbandonnes: {
    list: (params) =>
      api.get('/marketing/relances-devis-abandonnes/', { params }),
  },

  // ── PACT106 — Avis clients + routage Google Reviews (FG239) ──
  avisClients: {
    ...resource('avis-clients'),
    // Enregistre note/témoignage reçus (statut sollicité -> reçu).
    recevoir: (id, data) =>
      api.post(`/marketing/avis-clients/${id}/recevoir/`, data),
    // Route vers Google Reviews si GOOGLE_REVIEW_URL est configuré côté
    // serveur — NO-OP propre sinon (avis renvoyé inchangé, jamais une erreur).
    pousserGoogle: (id) =>
      api.post(`/marketing/avis-clients/${id}/pousser_google/`),
  },

  // ── PACT107 — Enquêtes NPS post-installation (FG238), distinctes du Pulse
  // eNPS interne employés et du générique `Enquete` ──
  enquetesNps: {
    ...resource('enquetes-nps'),
    // Enregistre la note (0-10) + commentaire d'un client (statut envoyée -> répondue).
    repondre: (id, data) =>
      api.post(`/marketing/enquetes-nps/${id}/repondre/`, data),
    // Score NPS consolidé de la société (%promoteurs - %détracteurs) — calculé
    // côté serveur, jamais recalculé ici.
    score: () => api.get('/marketing/enquetes-nps/score/'),
  },

  // ── PACT108 — Journal des messages WhatsApp entrants (FG207), LECTURE SEULE ──
  messagesWhatsapp: {
    list: (params) => api.get('/marketing/messages-whatsapp/', { params }),
  },

  // ── NTMKT26 — Import CSV de coûts publicitaires externes (Meta/Google Ads) ──
  // Aucun appel API externe : un fichier CSV exporté à la main est réconcilié
  // par nom de campagne avec `cout_reel_mad` (XMKT17).
  importerCoutsPublicitaires: (fichier) => {
    const form = new FormData()
    form.append('fichier', fichier)
    return api.post('/marketing/campagnes/importer-couts/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // ── NTMKT27 — Bilan de campagne PDF interne (jamais un devis client) ──
  rapportCampagnePdf: (id) =>
    api.get(`/marketing/campagnes/${id}/rapport-pdf/`, { responseType: 'blob' }),

  // ── NTMKT28 — Export PDF du registre de consentement (CNDP) ──
  registreConsentementExportPdf: (params) =>
    api.get('/marketing/registre-consentement/export-pdf/', {
      params, responseType: 'blob',
    }),

  // ── NTMKT31 — Réglages tenant du module Marketing (singleton société) ──
  parametres: {
    get: () => api.get('/marketing/parametres/'),
    maj: (data) => api.patch('/marketing/parametres/', data),
  },

  // ── NTMKT18/19 — Score de maturité d'un lead (badge chaud/tiède/froid +
  // sparkline sur la fiche/kanban). Distinct du score de qualité QJ6 (déjà
  // porté par le lead lui-même) : { actif, valeur, historique }. ──
  scoreMaturite: {
    get: (leadId) => api.get(`/marketing/scores-maturite/${leadId}/`),
  },
}

export default marketingApi
