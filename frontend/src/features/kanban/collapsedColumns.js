// LB10 — Persistance PURE (zéro React) du repli de colonnes kanban
// (docs/design/leads-board-blueprint.md D2). `KanbanView.jsx` lit l'état
// initial via `readCollapsedStages()` et écrit à chaque bascule via
// `writeCollapsedStages()` — jamais de repli par défaut (tableau vide tant
// que rien n'a été replié). Tolérant aux clés inconnues (une étape retirée
// de stages.js dans une session future ne fait jamais planter la lecture),
// tolérant à l'absence de stockage (mode privé / SSR / test) — jamais un
// throw qui casserait le rendu du board. Testable `node --test`
// (zéro dépendance React/DOM réelle).
import { PIPELINE_STAGES } from '../crm/stages.js'

export const COLLAPSED_STORAGE_KEY = 'taqinor.leads.kanban.collapsed'

// Tableau des clés d'étape actuellement repliées (STAGES.py, jamais une
// autre liste). `[]` en repli sur toute anomalie (stockage absent, JSON
// corrompu, valeur qui n'est pas un tableau) — aucun repli n'est perdu de
// façon visible : au pire, tout redevient déplié.
export function readCollapsedStages() {
  try {
    const raw = window.localStorage.getItem(COLLAPSED_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((k) => PIPELINE_STAGES.includes(k))
  } catch {
    // `window` absent (SSR/test), stockage indisponible (navigation privée),
    // ou JSON corrompu — jamais un throw qui empêcherait le board de rendre.
    return []
  }
}

export function writeCollapsedStages(stages) {
  try {
    window.localStorage.setItem(
      COLLAPSED_STORAGE_KEY,
      JSON.stringify([...new Set((stages ?? []).filter((k) => PIPELINE_STAGES.includes(k)))]),
    )
  } catch {
    // Quota dépassé / navigation privée : perte silencieuse — le repli reste
    // fonctionnel pour la session en cours, juste pas persisté.
  }
}
