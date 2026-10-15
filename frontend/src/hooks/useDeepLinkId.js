import { useMemo } from 'react'

/* Lien profond `?id=<pk>` PARTAGÉ des listes (chantiers, interventions, tickets,
   clients) : l'élément ciblé est DÉRIVÉ des éléments chargés (aucun effet), et
   fermer le panneau retire le paramètre pour ne pas rouvrir la fiche. Un id
   absent des éléments chargés laisse `deepItem` à null (l'appelant décide de
   l'afficher comme « introuvable » une fois le chargement terminé). */
export function useDeepLinkId(searchParams, setSearchParams, items) {
  const wantedId = searchParams.get('id')
  const deepItem = useMemo(() => {
    if (!wantedId) return null
    return (items ?? []).find((it) => String(it.id) === String(wantedId)) ?? null
  }, [wantedId, items])
  const clearDeepLink = () => {
    if (searchParams.has('id')) {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.delete('id')
        return next
      }, { replace: true })
    }
  }
  return { wantedId, deepItem, clearDeepLink }
}
