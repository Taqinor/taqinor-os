import api from './axios'
import { makeResourceFactory, unwrapList } from './resource'
import { downloadBlobInGesture } from '../utils/downloadBlob'

/* ============================================================================
   NTMKT1 — Client API du module « Marketing » (apps/marketing).
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /marketing/... »
   (préfixe ODX10, `apps/marketing/urls.py` — sert les MÊMES ViewSets que
   l'ancien préfixe historique `/compta/...` consommé par
   `CampagnesScreen.jsx`/`comptaApi.campagnes`, jamais touché ici). Un seul
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

  // ── WIR161 — Journal d'appels commercial / click-to-call log (FG208) ──
  // `company`/`auteur` posés côté serveur (jamais lus du corps de requête).
  appels: resource('appels'),
}

export default marketingApi
