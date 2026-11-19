import { useEffect, useEffectEvent, useMemo, useState } from 'react'

/* Lien profond `?id=<pk>` PARTAGÉ des listes (chantiers, interventions, tickets,
   clients) : l'élément ciblé est DÉRIVÉ des éléments chargés, et fermer le panneau
   retire le paramètre pour ne pas rouvrir la fiche.

   Un id absent des éléments chargés (liste filtrée côté serveur — « Mes chantiers » —,
   ou objet que la fiche autorise mais que la liste ne montre pas) : si l'appelant donne
   `fetchById` (id -> promesse axios), l'objet est lu PAR SON ID, une fois la liste prête
   (`pret`). Pendant la lecture `deepLoading` est vrai ; si le serveur répond une erreur
   (404 compris), `deepItem` reste null une fois `deepLoading` retombé : l'appelant affiche
   alors « introuvable » — jamais un chargement sans fin. */
export function useDeepLinkId(searchParams, setSearchParams, items, { fetchById, pret = true } = {}) {
  const wantedId = searchParams.get('id')
  const dansListe = useMemo(() => {
    if (!wantedId) return null
    return (items ?? []).find((it) => String(it.id) === String(wantedId)) ?? null
  }, [wantedId, items])
  // Résultat de la lecture par id : { id, item } (item null = introuvable).
  const [lu, setLu] = useState(null)
  const aLire = !!wantedId && !dansListe && pret && !!fetchById
  const lire = useEffectEvent((id) => fetchById(id))
  useEffect(() => {
    if (!aLire) return undefined
    let annule = false
    lire(wantedId)
      .then((res) => { if (!annule) setLu({ id: wantedId, item: res?.data ?? null }) })
      .catch(() => { if (!annule) setLu({ id: wantedId, item: null }) })
    return () => { annule = true }
  }, [aLire, wantedId])
  const luPourCetId = lu && lu.id === wantedId ? lu : null
  const deepItem = dansListe ?? luPourCetId?.item ?? null
  const deepLoading = aLire && !luPourCetId
  const clearDeepLink = () => {
    if (searchParams.has('id')) {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.delete('id')
        return next
      }, { replace: true })
    }
  }
  return { wantedId, deepItem, deepLoading, clearDeepLink }
}
