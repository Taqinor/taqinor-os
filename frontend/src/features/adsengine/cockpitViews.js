/* ============================================================================
   PUB43 — Vues enregistrées un-clic du Cockpit (logique PURE, sans JSX).
   ----------------------------------------------------------------------------
   4 onglets prédéfinis + « Toutes » : filtre + tri FIGÉS, calculés uniquement
   sur les métriques DÉJÀ produites par ``metrics.ads_cockpit_rows``  — aucune
   valeur inventée, aucun nouveau champ. + mémoire du dernier onglet/tri choisi
   (localStorage, dégradation silencieuse si indisponible — mode privé/quota).
   ========================================================================== */
import { sortCockpitRows } from './adsengine'

export const COCKPIT_VIEWS = [
  { key: 'toutes', label: 'Toutes' },
  { key: 'top', label: 'Top Ads' },
  { key: 'fatigue', label: 'En fatigue' },
  { key: 'baisse', label: 'En baisse' },
  { key: 'videos', label: 'Meilleures vidéos' },
]

// Applique le filtre+tri FIGÉ d'un onglet prédéfini (« toutes » renvoie la
// liste telle quelle — le tri manuel par colonne reste maître dans ce cas).
export function applyCockpitView(rows, viewKey) {
  const list = rows || []
  switch (viewKey) {
    // Top Ads : signatures RÉELLES (>0) triées par coût/signature croissant
    // (le meilleur ROI en tête) — jamais une ad sans signature « en tête ».
    case 'top':
      return sortCockpitRows(
        list.filter(r => Number(r.signatures) > 0),
        'cost_per_signature_mad', 'asc')
    // En fatigue : le détecteur backend (ADSDEEP45) a DÉCLENCHÉ, toute
    // sévérité — triées par dépense décroissante (le plus gros risque d'abord).
    case 'fatigue':
      return sortCockpitRows(
        list.filter(r => r.fatigue?.fired === true),
        'depense_mad', 'desc')
    // En baisse : fatigue CONFIRMÉE (sévérité critique, pas seulement
    // possible) — triées par coût/signature décroissant (la dégradation la
    // plus coûteuse d'abord).
    case 'baisse':
      return sortCockpitRows(
        list.filter(r => r.fatigue?.fired === true && r.fatigue?.severity === 'critique'),
        'cost_per_signature_mad', 'desc')
    // Meilleures vidéos : format vidéo uniquement, triées par coût/signature
    // croissant (même logique que Top Ads, restreinte au format).
    case 'videos':
      return sortCockpitRows(
        list.filter(r => r.thumbnail_kind === 'video'),
        'cost_per_signature_mad', 'asc')
    default:
      return list
  }
}

const STORAGE_KEY = 'ae-cockpit-view'

// Dernière vue enregistrée ({ tab, sort }) — ``null`` si absente/invalide/
// indisponible (jamais une erreur qui casse le montage de l'écran).
export function loadSavedCockpitView() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

export function saveCockpitView(state) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // localStorage indisponible (mode privé, quota dépassé…) : dégradation
    // silencieuse — la mémoire de vue n'est qu'un confort, jamais bloquant.
  }
}
