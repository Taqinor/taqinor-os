import api from './axios'

const ventesApi = {
  // XSAL3 — résolution de prix (liste client / palier de quantité), lecture
  // seule, company-scoped (backend `prix_applicable_view`, XSAL1 `ListePrix`
  // + XSAL2 `RegleListePrix` en place). Renvoie { prix, source, liste_nom } —
  // le fallback `prix_vente` standard reste calculé côté serveur, jamais
  // deviné ici.
  getPrixApplicable: ({ produit, client, quantite } = {}) =>
    api.get('/ventes/prix-applicable/', { params: { produit, client, quantite } }),

  // XSAL1-2 — administration des listes de prix (CRUD + lignes/règles).
  getListesPrix: (params) => api.get('/ventes/listes-prix/', { params }),
  getListePrix: (id) => api.get(`/ventes/listes-prix/${id}/`),
  createListePrix: (data) => api.post('/ventes/listes-prix/', data),
  updateListePrix: (id, data) => api.put(`/ventes/listes-prix/${id}/`, data),
  patchListePrix: (id, data) => api.patch(`/ventes/listes-prix/${id}/`, data),
  deleteListePrix: (id) => api.delete(`/ventes/listes-prix/${id}/`),
  // Upsert (crée ou met à jour) le prix d'un produit dans une liste.
  setLignePrixListe: (listeId, { produit, prix_unitaire }) =>
    api.post(`/ventes/listes-prix/${listeId}/lignes/`, { produit, prix_unitaire }),
  // Ajoute une règle de prix / palier de quantité à une liste.
  addRegleListePrix: (listeId, data) =>
    api.post(`/ventes/listes-prix/${listeId}/regles/`, data),

  // Devis
  // VX55 — `config` optionnel (ex. { signal }) pour l'annulation
  // AbortController câblée depuis fetchDevis (createAsyncThunk {signal}).
  getDevis: (params, config) => api.get('/ventes/devis/', { params, ...config }),
  getDevisById: (id) => api.get(`/ventes/devis/${id}/`),
  createDevis: (data) => api.post('/ventes/devis/', data),
  // QX21 — création ATOMIQUE (devis + lignes en un seul commit serveur) : plus
  // de brouillons orphelins/partiels si la connexion est coupée en cours de
  // sauvegarde. `data` porte le devis + une clé `lignes: [...]`.
  createDevisAtomic: (data) => api.post('/ventes/devis/atomic/', data),
  // QX21 — remplacement ATOMIQUE des lignes d'un devis (édition) : les
  // anciennes lignes sont remplacées par les nouvelles en une transaction ; un
  // échec préserve les lignes existantes (jamais un devis à zéro ligne).
  replaceLignesDevis: (id, lignes) =>
    api.post(`/ventes/devis/${id}/replace-lines/`, { lignes }),
  updateDevis: (id, data) => api.put(`/ventes/devis/${id}/`, data),
  patchDevis: (id, data) => api.patch(`/ventes/devis/${id}/`, data),
  deleteDevis: (id) => api.delete(`/ventes/devis/${id}/`),
  genererPdfDevis: (id, options = {}) => api.post(`/ventes/devis/${id}/generer-pdf/`, options),
  telechargerPdfDevis: (id) => api.get(`/ventes/devis/${id}/telecharger-pdf/`, { responseType: 'blob' }),
  // Proposition client (chemin canonique /proposal) — rendue à la volée selon
  // le format (pdf_mode/onepage/full, include_etude…), récupérée en blob pour
  // l'aperçu inline (iframe) ET le téléchargement, sans quitter la fiche lead.
  getProposalPdf: (id, params = {}) =>
    api.get(`/ventes/devis/${id}/proposal/`, { params, responseType: 'blob' }),
  convertirDevisEnBC: (id) => api.post(`/ventes/devis/${id}/convertir-bc/`),
  // B2/WR2 — (re)mint le lien public de proposition sans passer par l'envoi
  // email/WhatsApp (ex. pour le copier manuellement).
  shareLinkDevis: (id) => api.post(`/ventes/devis/${id}/share-link/`),
  // Révision : crée une nouvelle version (v2, v3…) d'un devis.
  reviserDevis: (id) => api.post(`/ventes/devis/${id}/reviser/`),
  // PV20 — TOUT ce que l'écran de conception 3D doit savoir d'un devis, en UN
  // SEUL appel : identité + statut, géométrie déjà enregistrée (roof_layout /
  // pin / contour), cible vendue (panneaux, kWc, scénario), disponibilité de la
  // carte, et `modifiable` + `raison_lecture_seule` — le motif de la lecture
  // seule vient TOUJOURS du serveur, jamais rédigé côté écran. Forme figée par
  // le contrat partagé `apps/ventes/contract_samples/devis_design_context.json`.
  getDevisDesignContext: (id) => api.get(`/ventes/devis/${id}/design-context/`),
  // PV21 — resynchronise les LIGNES du devis sur un nouveau calepinage. Mise à
  // jour CHIRURGICALE d'un brouillon (quantité de panneaux + présence batterie,
  // rien d'autre : prix négociés, remises, notes et groupes restent intacts) ;
  // le STATUT n'est jamais écrit. Corps : `{layout}`. Renvoyer le MÊME layout
  // ne fait aucune écriture (`inchange: true`). 409 `revision_possible: true` =
  // le client a déjà cette version sous les yeux, le bon geste est « Réviser » ;
  // 409 `revision_possible: false` = document clos (lecture seule).
  syncDevisLayout: (id, body) => api.post(`/ventes/devis/${id}/sync-layout/`, body),
  // PV22 — Copilote : crée un devis RÉSIDENTIEL automatiquement dimensionné
  // depuis la fiche lead (jamais un brouillon vide). Corps `{lead}` (ou
  // `{client}`). 422 + `detail` FR quand les données de dimensionnement
  // manquent ou que le marché n'est pas résidentiel : le message vient du
  // serveur et oriente vers le générateur complet.
  creerDevisAuto: (data) => api.post('/ventes/devis/auto/', data),
  // QJ14 — Envoyer par email : PDF premium + lien tokenisé → client, consigne EmailLog, marque envoyé.
  envoyerEmailDevis: (id, payload = {}) => api.post(`/ventes/devis/${id}/envoyer-email/`, payload),
  // QG8 — « Envoyer » = flux WhatsApp : lien wa.me + lien tokenisé, marque envoyé.
  whatsappDevis: (id, payload = {}) => api.post(`/ventes/devis/${id}/whatsapp/`, payload),
  // QX22 — aperçu LECTURE SEULE du message WhatsApp (aucune mutation de statut) :
  // peuple la modale d'aperçu ; seul le clic-through sur wa.me (whatsappDevis
  // ci-dessus) marque réellement le devis « Envoyé ».
  whatsappPreviewDevis: (id, payload = {}) => api.post(`/ventes/devis/${id}/whatsapp-preview/`, payload),
  // QJ28 — « Contacter mon supérieur » : notifie le supérieur du vendeur sur ce devis.
  contacterSuperieur: (id, payload = {}) => api.post(`/ventes/devis/${id}/contacter-superieur/`, payload),
  // VX215 — boucle de retour « pris en charge » : l'émetteur voit si sa
  // demande d'avis a été VUE par le(s) supérieur(s) notifié(s) ci-dessus.
  superiorContactStatus: (id) => api.get(`/ventes/devis/${id}/superior-contact-status/`),
  // QJ15 — Variantes : créer 2–3 copies dimensionnées pour comparaison côte-à-côte.
  dupliquerVariante: (id, payload = {}) => api.post(`/ventes/devis/${id}/dupliquer-variante/`, payload),
  // QJ15 — Lister les variantes liées à ce devis (même version_parent).
  getVariantes: (id) => api.get(`/ventes/devis/${id}/variantes/`),
  // GAMMES — crée la SŒUR « gamme » de ce devis (même mécanique de variantes :
  // devis frère complet, composition et prix propres). Corps : `nom`,
  // `nom_source`, `recommandee`. Le libellé est une DONNÉE, jamais une marque
  // codée en dur.
  dupliquerVarianteGamme: (id, payload = {}) =>
    api.post(`/ventes/devis/${id}/dupliquer-variante-gamme/`, payload),
  // PV41/PV43 — étude ÉLECTRIQUE agrégée du devis, en UN SEUL appel. GET la lit
  // (et la calcule si absente) ; POST la RECALCULE avec des surcharges
  // (`dc_m`/`ac_m`/`phases`/`regime`…). Les deux rendent EXACTEMENT la forme du
  // contrat partagé `apps/ventes/contract_samples/conception_electrique.json` —
  // jamais de prix/marge (règle du dépôt).
  getConceptionElectrique: (id) => api.get(`/ventes/devis/${id}/conception-electrique/`),
  recalculerConceptionElectrique: (id, overrides = {}) =>
    api.post(`/ventes/devis/${id}/conception-electrique/`, overrides),
  // PV40/PV43 — planche « schéma unifilaire » déduite du devis : `?format=json`
  // renvoie `{params, svg}` (aperçu inline), `?format=pdf` la même planche en
  // PDF (blob, jamais un document client — rule #4).
  getSchemaUnifilaireDevis: (id) =>
    api.get(`/ventes/devis/${id}/schema-unifilaire/`, { params: { format: 'json' } }),
  getSchemaUnifilairePdf: (id) =>
    api.get(`/ventes/devis/${id}/schema-unifilaire/`, {
      params: { format: 'pdf' }, responseType: 'blob',
    }),
  // PV74/PV76 — étude BANCABLE : lance le calcul (PVGIS par pan) en tâche de
  // fond → 202 + jeton, puis sonder `simulation-status` jusqu'à
  // `{status:'ready', simulation}`. La charge lue reste TOUJOURS
  // `Devis.etude_params.simulation` (jamais recopiée depuis le cache du job).
  simulerEtudeDevis: (id, payload = {}) => api.post(`/ventes/devis/${id}/simuler/`, payload),
  getSimulationStatus: (id, token) =>
    api.get(`/ventes/devis/${id}/simulation-status/${token}/`),
  // QG9/QG10 — lit (GET) ou règle (PUT, Directeur/Commercial responsable) le
  // pourcentage par défaut des variantes de devis.
  getVarianteConfig: () => api.get('/ventes/devis/variante-config/'),
  setVarianteConfig: (variante_pct) => api.put('/ventes/devis/variante-config/', { variante_pct }),
  // Approbation admin de la remise (T17) — débloque l'envoi.
  approuverRemise: (id) => api.post(`/ventes/devis/${id}/approuver-remise/`),
  // N25 — acceptation explicite (date + nom), déclencheur de chantier + chatter.
  accepterDevis: (id, payload = {}) => api.post(`/ventes/devis/${id}/accepter/`, payload),
  // WR1 — FG44 : refus explicite (motif/date/chatter), fait avancer le funnel
  // (devis_refused) — chemin canonique, à la place d'un PATCH statut direct.
  refuserDevis: (id, payload = {}) => api.post(`/ventes/devis/${id}/refuser/`, payload),
  // ── WIR104 — Cluster réglementaire / mise en service (FG245, FG268-287) ──
  // Décision consignée en tête de `apps/ventes/models_regulatory.py` : ces
  // données RESTENT dans `ventes` (dossier réglementaire de l'affaire), face à
  // `installations` (exécution physique). Elles étaient toutes complètes côté
  // serveur et sans aucun consommateur : cette lecture générique alimente
  // l'écran `/ventes/dossiers-reglementaires`. `resource` vient TOUJOURS d'une
  // liste blanche côté écran, jamais d'une saisie utilisateur.
  getReglementaire: (resource, params) =>
    api.get(`/ventes/${resource}/`, { params }),
  getCalendrierReglementaire: (params) =>
    api.get('/ventes/calendrier-reglementaire/', { params }),

  // ── WIR103 — Palier avancé facturation : note de débit + proforma ──
  // Les deux étaient complets et testés côté serveur mais n'avaient AUCUN
  // wrapper client (zéro UI). Le reste du palier (pénalités, encaissement
  // groupé, promesses, mandats, remises d'encaissement) reste en attente.
  // ZFAC4 — note de débit : créée DEPUIS une facture émise, puis lisible et
  // téléchargeable en PDF. Sans `lignes`, le serveur recopie la facture.
  creerNoteDebit: (factureId, data) =>
    api.post(`/ventes/factures/${factureId}/creer-note-debit/`, data || {}),
  getNotesDebit: (params) => api.get('/ventes/notes-debit/', { params }),
  telechargerNoteDebitPdf: (id) =>
    api.get(`/ventes/notes-debit/${id}/telecharger-pdf/`,
      { responseType: 'blob' }),
  // XFAC10 — proforma d'un devis : document sans impact comptable (jamais une
  // facture). Le POST renvoie directement le PDF.
  getProformaPdf: (devisId) =>
    api.post(`/ventes/devis/${devisId}/proforma-pdf/`, {},
      { responseType: 'blob' }),

  // WIR99/DC12 — pré-remplissage du générateur pour un devis SANS lead, depuis
  // le `crm.SiteProfile` du client (profil énergie/toiture/pompage réutilisable).
  getPrefillSite: (clientId) =>
    api.get('/ventes/devis/prefill-site/', { params: { client: clientId } }),
  // WIR96 — suivi marketing d'un devis : ouverture du lien de partage
  // (« vu le … ») + relances de devis abandonné consignées.
  getSuiviPartageDevis: (id) => api.get(`/ventes/devis/${id}/suivi-partage/`),
  historiqueDevis: (id) => api.get(`/ventes/devis/${id}/historique/`),
  noterDevis: (id, body) => api.post(`/ventes/devis/${id}/noter/`, { body }),
  // NTCPQ8 — approbation de remise par paliers (matrice NTCPQ7).
  approbationDevis: (id) => api.get(`/ventes/devis/${id}/approbation/`),
  approuverEtapeDevis: (id, commentaire = '') =>
    api.post(`/ventes/devis/${id}/approuver-etape/`, { commentaire }),
  rejeterEtapeDevis: (id, motif = '') =>
    api.post(`/ventes/devis/${id}/rejeter-etape/`, { motif }),
  // Export comptable : journal des ventes + résumé TVA (.xlsx) sur une période.
  journalVentes: (params) =>
    api.get('/ventes/journal-ventes/', { params, responseType: 'blob' }),
  // FE-SCA41 — statut d'un export xlsx volumineux parti en tâche de fond
  // (réponse 202 initiale de journalVentes / export-comptable) : poller
  // jusqu'à {status:'ready', download_url, filename} ou {status:'error'}.
  exportStatus: (jobId) => api.get(`/ventes/export/status/${jobId}/`),
  // Échéancier devis → factures : génère la prochaine tranche (acompte → solde).
  genererFacture: (id) => api.post(`/ventes/devis/${id}/generer-facture/`),
  // QX29 — « Relances du jour » : devis nécessitant une action (envoyés sans
  // réponse par palier de cadence, acceptés non facturés — réutilise le
  // sélecteur ZFAC12, refusés sans motif, expirant bientôt). Miroir de
  // savApi.getSavFileAction() (ZSAV6) — buckets { count, ids }.
  getDevisActionBoard: () => api.get('/ventes/devis/action-requise/'),

  // Lignes de devis
  getLignesDevis: (params) => api.get('/ventes/devis-lignes/', { params }),
  createLigneDevis: (data) => api.post('/ventes/devis-lignes/', data),
  updateLigneDevis: (id, data) => api.put(`/ventes/devis-lignes/${id}/`, data),
  deleteLigneDevis: (id) => api.delete(`/ventes/devis-lignes/${id}/`),

  // Bons de commande
  getBonsCommande: (params) => api.get('/ventes/bons-commande/', { params }),
  getBonCommande: (id) => api.get(`/ventes/bons-commande/${id}/`),
  createBonCommande: (data) => api.post('/ventes/bons-commande/', data),
  updateBonCommande: (id, data) => api.put(`/ventes/bons-commande/${id}/`, data),
  patchBonCommande: (id, data) => api.patch(`/ventes/bons-commande/${id}/`, data),
  confirmerBC: (id) => api.post(`/ventes/bons-commande/${id}/confirmer/`),
  marquerLivreBC: (id) => api.post(`/ventes/bons-commande/${id}/marquer-livre/`),
  // XSAL12 — livraison partielle : { lignes: [{ligne_devis, quantite}], date_livraison?, note? }.
  livrerPartielBC: (id, data) => api.post(`/ventes/bons-commande/${id}/livrer-partiel/`, data),
  annulerBC: (id) => api.post(`/ventes/bons-commande/${id}/annuler/`),
  creerFactureBC: (id) => api.post(`/ventes/bons-commande/${id}/creer-facture/`),
  // ZSAL8 — PDF imprimable du bon de commande (blob, aperçu/téléchargement inline).
  getBonCommandePdf: (id) => api.get(`/ventes/bons-commande/${id}/pdf/`, { responseType: 'blob' }),

  // Factures
  // VX163 — `config` (ex. `{signal}`) transmis pour l'annulation en vol.
  getFactures: (params, config) => api.get('/ventes/factures/', { params, ...config }),
  getFacture: (id) => api.get(`/ventes/factures/${id}/`),
  createFacture: (data) => api.post('/ventes/factures/', data),
  updateFacture: (id, data) => api.put(`/ventes/factures/${id}/`, data),
  patchFacture: (id, data) => api.patch(`/ventes/factures/${id}/`, data),
  genererPdfFacture: (id) => api.post(`/ventes/factures/${id}/generer-pdf/`),
  telechargerPdfFacture: (id) => api.get(`/ventes/factures/${id}/telecharger-pdf/`, { responseType: 'blob' }),
  envoyerEmailFacture: (id, email) => api.post(`/ventes/factures/${id}/envoyer-email/`, { email }),
  // Envoyer par WhatsApp : lien wa.me prêt à envoyer (modele 'facture'/'relance').
  whatsappFacture: (id, payload = {}) => api.post(`/ventes/factures/${id}/whatsapp/`, payload),
  // N38 — export structuré UBL 2.1 (aperçu BROUILLON, jamais transmis) en XML.
  telechargerUbl: (id) => api.get(`/ventes/factures/${id}/ubl/`, { responseType: 'blob' }),
  // N31 — audit admin de la numérotation séquentielle (trous/doublons).
  auditNumerotation: () => api.get('/ventes/numerotation-audit/'),
  emettreFacture: (id) => api.post(`/ventes/factures/${id}/emettre/`),
  marquerPayeeFacture: (id) => api.post(`/ventes/factures/${id}/marquer-payee/`),
  annulerFacture: (id) => api.post(`/ventes/factures/${id}/annuler/`),
  // Paiements : enregistrement manuel + liste par facture.
  enregistrerPaiement: (id, data) => api.post(`/ventes/factures/${id}/enregistrer-paiement/`, data),
  getPaiementsFacture: (id) => api.get(`/ventes/factures/${id}/paiements/`),
  // ZFAC11 — reste à payer arrondi au pas de caisse société pour un règlement
  // espèces (applicable=false + montant_du inchangé si arrondi désactivé).
  arrondiCaisseFacture: (id, mode = 'especes') =>
    api.get(`/ventes/factures/${id}/arrondi-caisse/`, { params: { mode } }),
  // FG53/WR2 — lien « Payer en ligne » (fournisseur NoOp par défaut, gated).
  lienPaiementFacture: (id, payload = {}) => api.post(`/ventes/factures/${id}/lien-paiement/`, payload),
  // N105/WR2 — export + contrôle de conformité DGI (404 tant que le flag
  // société `dgi_export_actif` est OFF — comportement invisible par défaut).
  dgiExportFacture: (id) => api.get(`/ventes/factures/${id}/dgi-export/`, { responseType: 'blob' }),
  dgiConformiteFacture: (id) => api.get(`/ventes/factures/${id}/dgi-conformite/`),
  // FG43/WR2 — actions en masse (émettre/relancer/email/pdf) sur une sélection.
  bulkFactures: (action, ids) => api.post('/ventes/factures/bulk/', { action, ids }),
  // Encaissements : liste lecture seule de TOUS les paiements de la société
  // (PaiementViewSet), bornée serveur. ?ordering= pour le tri.
  getPaiements: (params) => api.get('/ventes/paiements/', { params }),

  // Avoirs (notes de crédit)
  creerAvoir: (factureId, data) => api.post(`/ventes/factures/${factureId}/creer-avoir/`, data),
  getAvoirs: (params) => api.get('/ventes/avoirs/', { params }),
  annulerAvoir: (id) => api.post(`/ventes/avoirs/${id}/annuler/`),
  telechargerAvoirPdf: (id) => api.get(`/ventes/avoirs/${id}/telecharger-pdf/`, { responseType: 'blob' }),

  // Recouvrement (vue/consigne/impression — jamais d'envoi)
  getRelances: () => api.get('/ventes/relances/'),
  relancerFacture: (id, data) => api.post(`/ventes/factures/${id}/relancer/`, data),
  exclureRelance: (id, exclu) => api.post(`/ventes/factures/${id}/exclure-relance/`, { exclu }),
  getRelancesFacture: (id) => api.get(`/ventes/factures/${id}/relances/`),
  // N87 — fil des emails (envoyés/reçus) d'une facture + état du compte d'envoi.
  getEmailsFacture: (id) => api.get(`/ventes/factures/${id}/emails/`),
  getEmailConfig: () => api.get('/ventes/email-config/'),
  getBalanceAgee: () => api.get('/ventes/balance-agee/'),
  // WIR84 — agrégateurs Quote-to-Cash de ventes (FG45 / FG47 / ZFAC10),
  // complets côté serveur mais sans aucun consommateur jusqu'ici. Ils sont
  // désormais lus par l'écran `/reporting/quote-to-cash` (QuoteToCashPage) —
  // aucun agrégateur mort ne reste dans `apps/ventes`.
  getDashboardQuoteToCash: (params) => api.get('/ventes/dashboard/', { params }),
  getCashFlowForecast: (params) => api.get('/ventes/insights/cash-flow/', { params }),
  getAnalyseFacturation: (params) =>
    api.get('/ventes/etats/analyse-facturation/', { params }),
  getClientReleve: (clientId) => api.get(`/ventes/clients/${clientId}/releve/`),
  getClientRelevePdf: (clientId) => api.get(`/ventes/clients/${clientId}/releve-pdf/`, { responseType: 'blob' }),
  getLettreRelancePdf: (factureId) => api.get(`/ventes/factures/${factureId}/lettre-relance-pdf/`, { responseType: 'blob' }),
  // Lettre de relance PREMIUM (langage visuel du devis) — niveau 1/2/3.
  getLettreRelancePremiumPdf: (factureId, niveau = 1) =>
    api.get(`/ventes/factures/${factureId}/lettre-relance-premium/`, {
      params: { niveau }, responseType: 'blob',
    }),
  // Fiche de remise / garantie après-vente PREMIUM pour un chantier.
  getFicheRemisePremiumPdf: (chantierId) =>
    api.get(`/ventes/chantiers/${chantierId}/fiche-remise-premium/`, { responseType: 'blob' }),
  getNiveauxRelance: () => api.get('/ventes/niveaux-relance/'),
  saveNiveauRelance: (id, data) => id
    ? api.patch(`/ventes/niveaux-relance/${id}/`, data)
    : api.post('/ventes/niveaux-relance/', data),
  deleteNiveauRelance: (id) => api.delete(`/ventes/niveaux-relance/${id}/`),
  // L768 — crée les niveaux par défaut (J+7 / J+15 / J+30) si aucun n'existe.
  seedNiveauxRelance: () => api.post('/ventes/niveaux-relance/seed-defaults/'),
  // L770/L786 — aperçu du prochain numéro RÉEL par type de pièce.
  numerotationPreview: () => api.get('/ventes/numerotation-preview/'),

  // Lignes de facture
  getLignesFacture: (params) => api.get('/ventes/factures-lignes/', { params }),
  createLigneFacture: (data) => api.post('/ventes/factures-lignes/', data),
  updateLigneFacture: (id, data) => api.put(`/ventes/factures-lignes/${id}/`, data),
  deleteLigneFacture: (id) => api.delete(`/ventes/factures-lignes/${id}/`),

  // QJ16 — Modèles de devis (presets)
  getPresets: (params) => api.get('/ventes/presets/', { params }),
  savePreset: (devisId, data) => api.post(`/ventes/devis/${devisId}/save-preset/`, data),
  applyPreset: (devisId, data) => api.post(`/ventes/devis/${devisId}/apply-preset/`, data),
  deletePreset: (id) => api.delete(`/ventes/presets/${id}/`),
}

export default ventesApi
