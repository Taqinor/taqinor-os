// LB49 — vues enregistrées DE COMPTE (retour fondateur 2026-07-20) : liées à
// l'utilisateur côté serveur (crm.SavedView), plus jamais au navigateur.
// Contrat : `views` triées par rank (la n°1 = défaut de connexion), CRUD +
// réordonnancement optimistes-simples (refetch après chaque écriture — les
// listes sont minuscules, la fraîcheur prime).
// `useSavedViews` (localStorage) reste le hook des AUTRES écrans
// (ClientList…) — celui-ci est le variant serveur, page leads d'abord.
import { useCallback, useEffect, useState } from 'react'
import crmApi from '../api/crmApi'

export function useAccountViews(page) {
  const [views, setViews] = useState([])
  // `loaded` distingue « liste vide » de « pas encore répondu » : le défaut
  // rang-1 ne doit s'appliquer qu'après une VRAIE réponse.
  const [loaded, setLoaded] = useState(false)

  const refresh = useCallback(() => crmApi.listSavedViews(page)
    .then((r) => {
      const d = r.data
      setViews(Array.isArray(d) ? d : (d?.results ?? []))
      setLoaded(true)
    })
    .catch(() => { setLoaded(true) }), [page])

  useEffect(() => { refresh() }, [refresh])

  const saveView = useCallback(async (name, payload) => {
    const trimmed = (name || '').trim()
    if (!trimmed) return false
    try {
      await crmApi.createSavedView({ page, name: trimmed, payload })
      await refresh()
      return true
    } catch {
      return false
    }
  }, [page, refresh])

  const deleteView = useCallback(async (id) => {
    try {
      await crmApi.deleteSavedView(id)
      await refresh()
      return true
    } catch {
      return false
    }
  }, [refresh])

  // Déplace une vue d'un cran (dir = -1 monte / +1 descend) puis pousse
  // l'ordre COMPLET au serveur (action reorder : rank = index).
  const moveView = useCallback(async (id, dir) => {
    const idx = views.findIndex((v) => v.id === id)
    const to = idx + dir
    if (idx < 0 || to < 0 || to >= views.length) return false
    const ids = views.map((v) => v.id)
    ;[ids[idx], ids[to]] = [ids[to], ids[idx]]
    try {
      await crmApi.reorderSavedViews(page, ids)
      await refresh()
      return true
    } catch {
      return false
    }
  }, [views, page, refresh])

  return { views, loaded, saveView, deleteView, moveView, refresh }
}

export default useAccountViews
