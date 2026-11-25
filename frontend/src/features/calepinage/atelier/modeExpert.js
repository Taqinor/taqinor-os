import { useCallback, useContext, useEffect, useMemo, useSyncExternalStore } from 'react'
import { store } from '../../../store'
import { ContextePresentation } from './coque/contexteCoque'

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

/* ACAL1438 — UN SEUL état partagé par tous les composants de l'atelier (rail, bandeau, Image HD, Résultats) : le choix
   vit ici, par utilisateur, et chaque `useModeExpert` s'y abonne. Basculer dans l'un met les autres à jour sans recharger.
   La mémoire du navigateur (localStorage) reste la règle d'ACAL394 ; l'état partagé est vidé quand plus aucun composant
   n'est monté (le prochain montage relit le stockage). */
const abonnes = new Set()
const partage = new Map()

const lirePartage = (utilisateurId) => {
  const cle = cleModeExpert(utilisateurId)
  if (!partage.has(cle)) partage.set(cle, lireModeExpert(utilisateurId))
  return partage.get(cle)
}
const abonner = (f) => {
  abonnes.add(f)
  return () => {
    abonnes.delete(f)
    if (abonnes.size === 0) partage.clear()
  }
}

/** `[expert, basculer]` — `forceUrl` (`?mode=expert`) impose l'expert sans l'écrire.
    T4-X8-005 — sous « Montrer au client » (`ContextePresentation`), le mode n'est JAMAIS lu : guidé, toujours (ni la
    préférence mémorisée ni `?mode=expert` ne montrent au client l'adresse, la date de photo ou les outils de l'atelier). */
export function useModeExpert(forceUrl = false) {
  const presentation = useContext(ContextePresentation) !== null
  const utilisateurId = useMemo(() => {
    try { return store.getState()?.auth?.user?.id ?? null } catch { return null }
  }, [])
  const memorise = useSyncExternalStore(abonner, () => lirePartage(utilisateurId), () => false)
  const basculer = useCallback((valeur) => {
    partage.set(cleModeExpert(utilisateurId), Boolean(valeur))
    ecrireModeExpert(utilisateurId, valeur)
    abonnes.forEach((f) => f())
  }, [utilisateurId])
  const expert = !presentation && (forceUrl || memorise)
  // Le PONT vers les scripts de l'atelier (ACAL552, 584, 717 : ils lisent
  // `document.body.dataset.modeExpert === '1'`) : posé ici, et retiré au démontage
  // du DERNIER composant qui tient le mode.
  useEffect(() => {
    const corps = typeof document !== 'undefined' ? document.body : null
    if (!corps) return undefined
    if (expert) corps.dataset.modeExpert = '1'
    else delete corps.dataset.modeExpert
    return () => { if (abonnes.size === 0) delete corps.dataset.modeExpert }
  }, [expert])
  return [expert, basculer]
}
