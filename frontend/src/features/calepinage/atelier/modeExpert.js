import { useCallback, useEffect, useMemo, useState } from 'react'
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

/** `true` si le choix est mémorisé ; `false` si le stockage est refusé (navigation
    privée, quota) — l'écran fonctionne quand même, sans mémoire. */
export function ecrireModeExpert(utilisateurId, expert, stockage) {
  try {
    (stockage ?? stockageDefaut())?.setItem(cleModeExpert(utilisateurId), expert ? '1' : '0')
    return true
  } catch { return false }
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
  const expert = forceUrl || memorise
  // Le PONT vers les scripts de l'atelier (ACAL552, 584, 717 : ils lisent
  // `document.body.dataset.modeExpert === '1'`) : posé ici, l'UNIQUE endroit
  // qui tient le mode, et retiré au démontage de l'atelier.
  useEffect(() => {
    const corps = typeof document !== 'undefined' ? document.body : null
    if (!corps) return undefined
    if (expert) corps.dataset.modeExpert = '1'
    else delete corps.dataset.modeExpert
    return () => { delete corps.dataset.modeExpert }
  }, [expert])
  return [expert, basculer]
}
