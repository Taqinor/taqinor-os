// ENF22 — tooltip « pourquoi ce score », séparé du composant ScoreBadge.jsx (règle
// react-refresh/only-export-components). Déplacement pur.
// VX221 — construit le tooltip « pourquoi ce score » à partir de la
// décomposition exposée par le backend (score_reasons : [{label, points}]).
// On montre les 3 facteurs dominants (déjà triés par points décroissants côté
// serveur), ex. « +20 Facture élevée · +15 Canal · +12 Lead récent ». Sans
// décomposition (ancien payload), on retombe sur l'ancien libellé.
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
