// VX24 — ScoreBadge extrait de ListView.jsx vers un composant partagé : le
// score de qualité du lead n'existait jusqu'ici QUE dans la vue Liste ; VX24
// le pose aussi sur la carte Kanban (à côté du nom) et sur le bandeau de
// faits clés de la fiche lead (LeadSummaryBar).
// Présentation pure : aucune mutation, aucun appel réseau.

// Badge de score : couleur selon le libellé renvoyé par scoring.py.
// VX26 — dérivé des tokens de marque (design/tokens.css --score-*) au lieu
// de hex locaux.
const SCORE_COLORS = {
  Chaud: { bg: 'var(--score-chaud-bg)', color: 'var(--score-chaud-fg)', border: 'var(--score-chaud-border)' },
  Tiede: { bg: 'var(--score-tiede-bg)', color: 'var(--score-tiede-fg)', border: 'var(--score-tiede-border)' },
  Froid: { bg: 'var(--score-froid-bg)', color: 'var(--score-froid-fg)', border: 'var(--score-froid-border)' },
}

// VX221 — construit le tooltip « pourquoi ce score » à partir de la
// décomposition exposée par le backend (score_reasons : [{label, points}]).
// On montre les 3 facteurs dominants (déjà triés par points décroissants côté
// serveur), ex. « +20 Facture élevée · +15 Canal · +12 Lead récent ». Sans
// décomposition (ancien payload), on retombe sur l'ancien libellé.
// eslint-disable-next-line react-refresh/only-export-components -- scoreTooltip co-localisé (dev HMR only)
export function scoreTooltip(lead) {
  const s = lead?.score ?? 0
  const reasons = Array.isArray(lead?.score_reasons) ? lead.score_reasons : []
  if (!reasons.length) return `Score de qualité : ${s}/100`
  const top = reasons
    .slice(0, 3)
    .map((r) => `+${r.points} ${r.label}`)
    .join(' · ')
  return `Score de qualité : ${s}/100\n${top}`
}

/** @param {{score?: number, score_label?: string, score_reasons?: Array}} lead */
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
      title={scoreTooltip(lead)}
    >
      {s}
    </span>
  )
}
