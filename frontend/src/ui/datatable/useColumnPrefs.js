// NTUX16 — Préférences de colonnes mémorisées par écran ET par utilisateur.
// Le moteur `<DataTable>` gère déjà show/hide/reorder/resize/pin EN MÉMOIRE
// (H31/O166) ; ce hook ajoute une auto-persistance LÉGÈRE dans localStorage,
// appliquée par défaut AVANT toute vue sauvegardée (NTUX1 exige une action
// « sauvegarder » explicite — ceci ne l'exige pas). Clé par NAVIGATEUR (donc
// déjà « par utilisateur » en pratique, comme le reste des préférences client
// de l'app — cf. `useServerSavedViews.js` PREF_PREFIX). Indépendant du
// système de vues nommées : une vue sauvegardée appliquée réécrit l'état du
// moteur PAR-DESSUS ce défaut (`applyView` dans DataTable.jsx), ce hook ne
// pose que le point de départ pré-vue.
import { useCallback, useMemo } from 'react'

const PREFIX = 'taqinor.'
const SUFFIX = '.columnPrefs'

function keyFor(ecran) {
  return `${PREFIX}${ecran}${SUFFIX}`
}

/** Lit les préférences de colonnes stockées pour un écran, ou `null` si
 *  absentes/corrompues/localStorage indisponible (jamais bloquant). */
export function readColumnPrefs(ecran) {
  if (!ecran) return null
  try {
    const raw = localStorage.getItem(keyFor(ecran))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    // Garde-fou minimal : une forme inattendue (JSON valide mais pas un état
    // de colonnes) ne doit jamais faire planter le moteur au montage.
    if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.order)) return null
    return parsed
  } catch {
    return null
  }
}

/** Écrit les préférences de colonnes pour un écran (best-effort). */
export function writeColumnPrefs(ecran, state) {
  if (!ecran) return
  try {
    localStorage.setItem(keyFor(ecran), JSON.stringify(state))
  } catch {
    // localStorage indisponible (mode privé / quota) — silencieux, jamais bloquant.
  }
}

/**
 * useColumnPrefs(ecran) — renvoie `{ initialColumnState, onColumnStateChange }`
 * à passer TEL QUEL à `<DataTable initialColumnState=… onColumnStateChange=… />`.
 * `ecran` est le même identifiant stable que `useServerSavedViews`/NTUX1
 * (ex. 'stock.produits').
 */
export function useColumnPrefs(ecran) {
  // Lu UNE SEULE FOIS par écran (le moteur ne consomme la valeur initiale
  // qu'au montage — cf. commentaire NTUX16 dans useDataTable.js).
  const initialColumnState = useMemo(() => readColumnPrefs(ecran) || undefined, [ecran])
  const onColumnStateChange = useCallback((state) => writeColumnPrefs(ecran, state), [ecran])
  return { initialColumnState, onColumnStateChange }
}

export default useColumnPrefs
