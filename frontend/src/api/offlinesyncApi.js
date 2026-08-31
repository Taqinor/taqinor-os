import api from './axios'

// NTMOB1 — point de synchro hors-ligne UNIQUE (tous modules).
//
// `envoyerLot` est le `sender` des files par module de `lib/offlineOutbox.js` :
// il rejoue un paquet d'opérations accumulées hors réseau. Le serveur dédoublonne
// par `client_op_id`, donc un lot est SÛR À REJOUER en entier — même si la
// réponse du premier essai s'est perdue.
const offlinesyncApi = {
  envoyerLot: (ops) => api.post('/offlinesync/operations/batch/', { ops }),
  // Journal (lecture seule) : ce qui attend, ce qui a été appliqué, ce qui a
  // été refusé et pourquoi. Filtres facultatifs `statut` / `module`.
  listOperations: (params) => api.get('/offlinesync/operations/', { params }),
  getOperation: (id) => api.get(`/offlinesync/operations/${id}/`),
  // NTMOB2 — conflits de synchronisation : l'enregistrement cible a été modifié
  // par un autre acteur entre la mise en file et le rejeu. Rien n'a été
  // appliqué ; un humain tranche.
  listConflits: () => api.get('/offlinesync/operations/', {
    params: { statut: 'conflit' },
  }),
  // `choix` : 'mienne' | 'serveur' | 'fusion' ; `payload` UNIQUEMENT (et
  // obligatoirement) pour une fusion — c'est le corps recomposé à la main.
  resoudreConflit: (id, choix, payload) => api.post(
    `/offlinesync/operations/${id}/resoudre/`,
    payload === undefined ? { choix } : { choix, payload },
  ),
}

export default offlinesyncApi
