import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   IMMOBILIER (Groupe NTPRO) — client API du module Immobilier & facilities.
   ----------------------------------------------------------------------------
   Miroir FIN des ViewSets DRF de `apps/immobilier` (préfixe `/immobilier/`).
   Toutes les URLs sont relatives : l'intercepteur axios préfixe `/api/django`.
   ========================================================================== */

const crud = makeResourceFactory(api, '/immobilier')

const immobilierApi = {
  sites: crud('sites'),
  batiments: crud('batiments'),
  niveaux: crud('niveaux'),
  locaux: crud('locaux'),
  locataires: {
    ...crud('locataires'),
    resolveClient: (id) => api.post(`/immobilier/locataires/${id}/resolve-client/`),
  },
}

export default immobilierApi
