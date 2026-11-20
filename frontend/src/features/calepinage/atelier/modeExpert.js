import { useCallback, useMemo, useState } from 'react'
import { store } from '../../../store'

/* ============================================================================
   ACAL394 — LE « MODE EXPERT » DU RAIL, mémorisé PAR UTILISATEUR.
   Guidé par défaut pour tous. Mémoire de CE navigateur (localStorage), jamais
   du serveur : aucun réglage utilisateur inscriptible n'existe. Lecture et
   écriture sous `try/catch` (patron `calques.js::lireEtatCalques`) : un
   stockage indisponible laisse le guidé, sans erreur.
   ========================================================================== */

export const PARAM_MODE = 'mode'

export function cleModeExpert(utilisateurId) {
  return `calepinage.mode_expert.${utilisateurId ?? 'anonyme'}`
}

const stockageDefaut = () => (typeof localStorage !== 'undefined' ? localStorage : null)

export function lireModeExpert(utilisateurId, stockage) {
  try {
    return (stockage ?? stockageDefaut())?.getItem(cleModeExpert(utilisateurId)) === '1'
  } catch {
    return false
  }
}

export function ecrireModeExpert(utilisateurId, expert, stockage) {
  try {
    (stockage ?? stockageDefaut())?.setItem(cleModeExpert(utilisateurId), expert ? '1' : '0')
  } catch {
    // stockage refusé : l'écran fonctionne quand même, sans mémoire
  }
}

/** `[expert, basculer]` — `forceUrl` (`?mode=expert`) impose l'expert sans l'écrire. */
export function useModeExpert(forceUrl = false) {
  const utilisateurId = useMemo(() => {
    try { return store.getState()?.auth?.user?.id ?? null } catch { return null }
  }, [])
  const [memorise, setMemorise] = useState(() => lireModeExpert(utilisateurId))
  const basculer = useCallback((valeur) => {
    setMemorise(valeur)
    ecrireModeExpert(utilisateurId, valeur)
  }, [utilisateurId])
  return [forceUrl || memorise, basculer]
}
