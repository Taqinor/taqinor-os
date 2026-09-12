import api from './axios'

// NTUX7 — corbeille transverse 30 jours (apps.trash.ElementSupprime).
// Journal en LECTURE SEULE côté serveur ; la seule écriture possible est
// l'action `restaurer/`, qui route vers le `services.py` de l'app cible
// (jamais un accès direct au modèle). Réservé Directeur/Admin côté serveur
// (`IsAdminOrResponsableTier`) — écran `/parametres/corbeille`.
const trashApi = {
  // `params` : { page, type, depuis, jusqua, restaures } — tous optionnels.
  // `restaures=1` inclut aussi les éléments déjà restaurés (audit de
  // rétention, NTUX24) ; par défaut, seuls les éléments ENCORE en corbeille.
  listCorbeille: (params = {}) => api.get('/trash/corbeille/', { params }),
  restaurer: (id) => api.post(`/trash/corbeille/${id}/restaurer/`),
}

export default trashApi
