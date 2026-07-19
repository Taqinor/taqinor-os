// LW16 — Rampe « rotting » (pourrissement) : plus un lead stagne dans une
// étape, plus l'indicateur d'ancienneté chauffe (neutre → ambre → rouge).
//
// Module PUR (zéro import) → testable en `node --test` (rotting.test.mjs). Les
// seuils [ambre, rouge] sont indexés sur l'ORDRE de PIPELINE_STAGES
// (features/crm/stages.js, miroir strict de STAGES.py — règle #2) : AUCUNE clé
// d'étape en dur ici, seulement des index. Le composant StageControl fait la
// correspondance stage → index via `PIPELINE_STAGES.indexOf`, donc renommer une
// étape reste impossible sans passer par stages.js.
//
// Seuils (blueprint D3 / LW16) :
//   index 0 (NEW)         > 2 j ambre / > 5 j rouge
//   index 1 (CONTACTED)   > 7 j ambre / > 14 j rouge
//   index 2 (QUOTE_SENT)  > 7 j ambre / > 14 j rouge
//   index 3 (FOLLOW_UP)   > 14 j ambre / > 30 j rouge
//   index 4 (SIGNED)      aucun pourrissement
//   index 5 (COLD)        aucun pourrissement
export const STAGE_ROTTING_THRESHOLDS = [
  [2, 5],
  [7, 14],
  [7, 14],
  [14, 30],
  null,
  null,
]

// Seuils [ambre, rouge] pour l'étape à l'index donné (null hors plage / SIGNED /
// COLD).
export function thresholdsForIndex(index) {
  if (index == null || index < 0) return null
  return STAGE_ROTTING_THRESHOLDS[index] ?? null
}

// Niveau de pourrissement pour une ancienneté `days` et des seuils [ambre,
// rouge]. Renvoie 'ok' | 'warning' | 'danger'. `days` absent/invalide ou seuils
// absents (SIGNED/COLD) → 'ok' (jamais d'alerte fantôme).
export function rottingLevel(days, thresholds) {
  if (!thresholds) return 'ok'
  const n = Number(days)
  if (!Number.isFinite(n)) return 'ok'
  const [amber, red] = thresholds
  if (n > red) return 'danger'
  if (n > amber) return 'warning'
  return 'ok'
}
