// VX24 — ScoreBadge extrait de ListView.jsx vers un composant partagé : le
// score de qualité du lead n'existait jusqu'ici QUE dans la vue Liste ; VX24
// le pose aussi sur la carte Kanban (à côté du nom) et sur le bandeau de
// faits clés de la fiche lead (LeadSummaryBar).
// Présentation pure : aucune mutation, aucun appel réseau.

// Badge de score : couleur selon le libellé renvoyé par scoring.py.
const SCORE_COLORS = {
  Chaud: { bg: '#fef3c7', color: '#92400e', border: '#fcd34d' },
  Tiede: { bg: '#e0f2fe', color: '#0369a1', border: '#7dd3fc' },
  Froid: { bg: '#f1f5f9', color: '#64748b', border: '#cbd5e1' },
}

/** @param {{score?: number, score_label?: string}} lead */
export default function ScoreBadge({ lead }) {
  const score = lead?.score ?? null
  const label = lead?.score_label ?? null
  if (score === null && label === null) return <span className="lv-muted">—</span>
  const s = score ?? 0
  const lbl = label ?? (s >= 70 ? 'Chaud' : s >= 45 ? 'Tiede' : 'Froid')
  const c = SCORE_COLORS[lbl] ?? SCORE_COLORS.Froid
  return (
    <span
      className="lv-score-badge"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.border}` }}
      title={`Score de qualité : ${s}/100`}
    >
      {s}
    </span>
  )
}
