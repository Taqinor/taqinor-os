// NTUX12 — Favoris épinglés par utilisateur (apps.uxviews.FavoriUtilisateur).
// Hook générique consommé par `FavoriButton.jsx` (bouton étoile sur un écran
// de détail) et `FavorisWidget.jsx` (liste sidebar/dashboard) — UNE seule
// source de vérité pour éviter que les deux surfaces divergent après un
// pin/unpin. Strictement personnel côté serveur (get_queryset filtre déjà
// `owner=request.user`) : ce hook n'a donc jamais à filtrer par utilisateur
// lui-même.
import { useCallback, useEffect, useState } from 'react'
import uxviewsApi from '../../api/uxviewsApi'

function extractList(data) {
  return Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : [])
}

export function useFavoris() {
  const [favoris, setFavoris] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = useCallback(() => {
    setLoading(true)
    setError(null)
    return uxviewsApi.listFavoris()
      .then((res) => setFavoris(extractList(res.data)))
      .catch(() => setError('Impossible de charger les favoris.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { refresh() }, [refresh])

  const findFavori = useCallback(
    (modele, objectId) => favoris.find(
      (f) => f.modele === modele && String(f.object_id) === String(objectId),
    ),
    [favoris],
  )

  const isFavori = useCallback(
    (modele, objectId) => Boolean(findFavori(modele, objectId)),
    [findFavori],
  )

  // toggle — épingle si absent, retire si déjà présent. Renvoie la promesse
  // pour permettre à l'appelant de gérer chargement/erreur localement (ex.
  // FavoriButton affiche un toast si le serveur refuse — limite NTUX28, cible
  // déjà supprimée…).
  const toggle = useCallback((modele, objectId) => {
    const existing = findFavori(modele, objectId)
    const action = existing
      ? uxviewsApi.deleteFavori(existing.id)
      : uxviewsApi.createFavori(modele, objectId)
    return action.then((res) => { refresh(); return res })
  }, [findFavori, refresh])

  // reorder — NTUX21 (glisser-déposer) : persiste le nouvel ordre côté
  // serveur et adopte IMMÉDIATEMENT la liste renvoyée (déjà réordonnée par
  // `reordonner/`) sans attendre un second aller-retour.
  const reorder = useCallback((id, ordre) => uxviewsApi.reordonnerFavori(id, ordre)
    .then((res) => { setFavoris(extractList(res.data)); return res }), [])

  return { favoris, loading, error, refresh, isFavori, findFavori, toggle, reorder }
}

export default useFavoris
