import api from './axios'

/* ============================================================================
   Facturation électronique DGI (apps/einvoice, Groupe NTMAR). Préfixe
   `/einvoice/`. La génération est GATED côté serveur (`EINVOICE_ENABLED`,
   défaut '0') : `generer` renvoie 204 quand la fonctionnalité est désactivée.
   La transmission live est bloquée tant qu'aucune crédential DGI n'est
   configurée (no-op serveur).
   ========================================================================== */

const einvoiceApi = {
  list: (params) => api.get('/einvoice/factures-electroniques/', { params }),
  // NTMAR5 — génère l'e-facture UBL d'une ventes.Facture. mode 'dry_run' par
  // défaut. 204 = e-facturation désactivée (EINVOICE_ENABLED off).
  generer: (factureId, mode = 'dry_run') =>
    api.post('/einvoice/factures-electroniques/generer/', {
      facture_id: factureId, mode,
    }),
  // NTMAR8 — anomalies bloquantes avant transmission (conforme si liste vide).
  controler: (id) =>
    api.get(`/einvoice/factures-electroniques/${id}/controler/`),
  // NTMAR9 — télécharge le XML UBL de cette version (binaire).
  telecharger: (id) =>
    api.get(`/einvoice/factures-electroniques/${id}/telecharger/`, {
      responseType: 'blob',
    }),
  // PACT54/NTMAR7 — enregistre l'INTENTION de transmission (file d'attente).
  // Aucune requête réseau sortante tant que le flag + l'URL DGI ne sont pas
  // configurés : la transmission reste « en attente », jamais une erreur.
  transmettre: (id) =>
    api.post(`/einvoice/factures-electroniques/${id}/transmettre/`),
  // PACT54/NTMAR7 — historique des transmissions (lecture seule côté serveur).
  transmissions: (params) => api.get('/einvoice/transmissions/', { params }),
}

export default einvoiceApi
