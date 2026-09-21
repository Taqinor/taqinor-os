// VX231(c) — Persiste l'onglet actif d'une page compta dans l'URL, pour qu'un
// rechargement (ou un lien partagé/deep-link) rouvre le MÊME onglet au lieu de
// retomber sur le premier. API calquée sur useState :
//
//   const [tab, setTab] = useTabParam('apercu')          // ?onglet=…
//   const [etat, setEtat] = useTabParam('balance', 'etat')  // ?etat=…
//
// `param` personnalise la clé de query (défaut « onglet ») pour les pages qui
// en réservent une (ex. EtatsPage utilise « etat », aussi ciblée par les
// deep-links « Comparer au Grand-livre »). La navigation est en `replace` pour
// ne pas empiler une entrée d'historique par changement d'onglet.
import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

export function useTabParam(defaultTab, param = 'onglet') {
  const [searchParams, setSearchParams] = useSearchParams()
  const raw = searchParams.get(param)
  const tab = raw || defaultTab
  const setTab = useCallback((next) => {
    setSearchParams((prev) => {
      const p = new URLSearchParams(prev)
      // Onglet par défaut → URL propre (pas de ?param= superflu).
      if (!next || next === defaultTab) p.delete(param)
      else p.set(param, next)
      return p
    }, { replace: true })
  }, [setSearchParams, defaultTab, param])
  return [tab, setTab]
}

export default useTabParam
