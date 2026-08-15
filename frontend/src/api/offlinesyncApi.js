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
}

export default offlinesyncApi
