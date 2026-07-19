import api from './axios'

const parametresApi = {
  getProfile: () => api.get('/parametres/'),
  updateProfile: (data) => api.patch('/parametres/update/', data),
  uploadLogo: (formData) => api.post('/parametres/upload-logo/', formData),
  deleteLogo: () => api.delete('/parametres/delete-logo/'),
  uploadSignature: (formData) => api.post('/parametres/upload-signature/', formData),
  deleteSignature: () => api.delete('/parametres/delete-signature/'),
  // Modèles de message WhatsApp (FR + Darija) éditables.
  getMessages: () => api.get('/parametres/messages/'),
  saveMessage: (data) => api.put('/parametres/messages/', data),
  // N55 / L765 — journal d'audit des changements de paramètres (lecture seule).
  // Filtres possibles : { section: 'profil'|'messages', user, limit }.
  getAudit: (params) => api.get('/parametres/audit/', { params }),
  // VX233 — sections réellement présentes du journal d'audit (curées + extra en
  // base), pour construire le filtre dynamiquement (≥ 6 sections, dont
  // « tarification ») au lieu d'un <Select> à 2 options codées en dur.
  getAuditSections: () => api.get('/parametres/audit/sections/'),
  // N58 — statuts métier configurables (libellé/ordre/visibilité) par domaine.
  // Couche d'AFFICHAGE : les clés canoniques et les transitions restent figées.
  getStatutsEffective: (domaine) =>
    api.get('/parametres/statuts/effective/', { params: { domaine } }),
  saveStatuts: (domaine, statuts) =>
    api.put('/parametres/statuts/bulk/', { domaine, statuts }),
  // ZSAL5 — modèles d'e-mail éditables par clé (envoi_devis, etc.), parité
  // WhatsApp (getMessages/saveMessage). RENDU uniquement — jamais de statut
  // touché ici (apps/parametres/views_email.py EmailTemplateViewSet).
  getEmailTemplates: () => api.get('/parametres/email-templates/effective/'),
  saveEmailTemplates: (templates) =>
    api.put('/parametres/email-templates/bulk/', { templates }),
  // D2/N60/N67/N26/N59 — modèles de documents éditables (textes du devis).
  // Tout champ vide = repli moteur sur le littéral historique (PDF identique).
  getDocumentTemplates: () => api.get('/parametres/document-templates/'),
  updateDocumentTemplates: (data) =>
    api.patch('/parametres/document-templates/update/', data),
  // N64/N65 — tarification ONEE + hypothèses ROI/productible éditables.
  // Barème seedé sur les défauts ONEE TTC ; rien n'est codé en dur ailleurs.
  getTariffSettings: () => api.get('/parametres/tarification/'),
  updateTariffSettings: (data) =>
    api.patch('/parametres/tarification/update/', data),
  computeRoi: (data) => api.post('/parametres/tarification/roi/', data),
  getProductible: (params) =>
    api.get('/parametres/tarification/productible/', { params }),
  // N94 — surcharges de traduction de l'interface (par langue/clé), company-scopé.
  // `effective` renvoie { overrides: { locale: { key: value } } } — utilisé au
  // login pour fusionner par-dessus les catalogues statiques N93.
  getTranslationOverrides: () =>
    api.get('/parametres/traductions/effective/'),
  // Upsert/suppression en masse : items = [{ locale, key, value }] ;
  // value vide ("" / null) supprime la surcharge (retour au catalogue statique).
  saveTranslationOverrides: (items) =>
    api.put('/parametres/traductions/bulk/', { items }),
  // WIR66 — référentiels société (ARC23/24/27) : taux de TVA, conditions de
  // paiement, unités de mesure. Lecture pour tout rôle ; écriture réservée
  // admin/responsable côté serveur. `company` toujours forcée serveur.
  getTauxTva: () => api.get('/parametres/taux-tva/'),
  createTauxTva: (data) => api.post('/parametres/taux-tva/', data),
  updateTauxTva: (id, data) => api.patch(`/parametres/taux-tva/${id}/`, data),
  deleteTauxTva: (id) => api.delete(`/parametres/taux-tva/${id}/`),
  setDefautTauxTva: (id) => api.post(`/parametres/taux-tva/${id}/set_defaut/`),
  getConditionsPaiement: () => api.get('/parametres/conditions-paiement/'),
  createConditionPaiement: (data) =>
    api.post('/parametres/conditions-paiement/', data),
  updateConditionPaiement: (id, data) =>
    api.patch(`/parametres/conditions-paiement/${id}/`, data),
  deleteConditionPaiement: (id) =>
    api.delete(`/parametres/conditions-paiement/${id}/`),
  getUnitesMesure: () => api.get('/parametres/unites-mesure/'),
  createUniteMesure: (data) => api.post('/parametres/unites-mesure/', data),
  updateUniteMesure: (id, data) =>
    api.patch(`/parametres/unites-mesure/${id}/`, data),
  deleteUniteMesure: (id) => api.delete(`/parametres/unites-mesure/${id}/`),
}

export default parametresApi
