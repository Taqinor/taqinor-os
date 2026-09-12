// VTA8 — Client HTTP de l'app autonome VISITES (`apps/visites`, sortie du CRM).
//
// Les 13 fonctions de l'agrégat visite vivaient dans `api/crmApi.js` et
// tapaient `/crm/visites/...` ; elles sont désormais ICI et tapent
// `/visites/...`. Rien d'autre n'a changé : la FORME des réponses est celle
// committée dans `backend/django_core/apps/visites/contract_samples/` (PACT10)
// — `visite_terrain.json` pour l'agrégat (rendu à l'identique par TOUTES les
// actions mutantes, leçon #96) et `ma_journee.json` pour l'accueil terrain.
//
// `getLeadPhotoToit` N'EST PAS ici : la texture calée est une lecture du LEAD
// (`/crm/leads/<id>/photo-toit/`), elle reste dans `crmApi` — le builder 3D
// peint le toit sans rien connaître du module visite.
import api from './axios'

const visitesApi = {
  // VTA6 — accueil de l'app : la journée de l'utilisateur (jour + retards).
  // Contrat `ma_journee.json` : {date, en_retard_count, visites:[...]}.
  // `?tous=1` (valideurs seulement) élargit à l'équipe ; sans
  // `visites_valider`, le SERVEUR impose commercial=self de toute façon.
  getMaJournee: (params, config) => api.get('/visites/ma-journee/', { params, ...config }),

  getVisites: (params, config) => api.get('/visites/visites/', { params, ...config }),
  getVisite: (id) => api.get(`/visites/visites/${id}/`),
  createVisite: (data) => api.post('/visites/visites/', data),

  // `fichier` est un File (CameraCapture/FileUpload) ; `slotCode` = le code du
  // slot ciblé (checklist[].slots[].code) — jamais un slot inventé côté écran.
  uploadVisitePhoto: (id, { slotCode, fichier, gpsLat, gpsLng, commentaire }) => {
    const form = new FormData()
    form.append('slot_code', slotCode)
    form.append('fichier', fichier)
    if (gpsLat != null) form.append('gps_lat', gpsLat)
    if (gpsLng != null) form.append('gps_lng', gpsLng)
    if (commentaire) form.append('commentaire', commentaire)
    return api.post(`/visites/visites/${id}/photos/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteVisitePhoto: (id, mediaId) => api.delete(`/visites/visites/${id}/photos/${mediaId}/`),

  // `valeurs` : objet plat des champs de la catégorie (mêmes clés que
  // `mesures.<categorie>` du contrat). 400 possible : `{erreurs:{champ:msg}}`.
  patchVisiteMesures: (id, categorie, valeurs) =>
    api.patch(`/visites/visites/${id}/mesures/`, { categorie, valeurs }),

  // 400 possible : `{manquants:[...], message}` — l'écran affiche la liste du
  // serveur, jamais une re-dérivation locale.
  terminerVisite: (id) => api.post(`/visites/visites/${id}/terminer/`),
  validerVisite: (id) => api.post(`/visites/visites/${id}/valider/`),
  // `payload` : {photos:[slot_code,...], mesures:[{categorie,champ},...], motif}
  // — `motif` OBLIGATOIRE côté serveur ET côté écran (VT8).
  renvoyerVisite: (id, payload) => api.post(`/visites/visites/${id}/renvoyer/`, payload),

  // VT9/VT11 — assemblage serveur (Celery) des photos du slot toiture ;
  // `photo_toit.assemblage_etat` passe en_cours→ok/echec, à relire par polling
  // (GET visite) — cet appel ne fait que déclencher la tâche.
  assemblerPhotosVisite: (id) => api.post(`/visites/visites/${id}/assembler-photos/`),
  // VT11 — sauvegarde du calage (4 coins [lat,lng] du drapage sur le contour).
  patchVisiteCalage: (id, coins) =>
    api.patch(`/visites/visites/${id}/calage/`, { texture_calage: { coins } }),

  // VTA6 — progression terrain. Horodatage SERVEUR (`en_route_le`/`arrivee_le`
  // de l'agrégat), idempotentes, réservées à l'assigné : l'écran n'invente
  // JAMAIS l'heure localement, il réaffiche celle que le serveur renvoie.
  demarrerRouteVisite: (id) => api.post(`/visites/visites/${id}/demarrer-route/`),
  arriverVisite: (id) => api.post(`/visites/visites/${id}/arriver/`),
}

export default visitesApi
