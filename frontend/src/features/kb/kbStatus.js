import { statusPill } from '../../ui/module'

/* ============================================================================
   UX43 — Taxonomie de statut d'un article de la base de connaissances.
   ----------------------------------------------------------------------------
   Miroir 1:1 de ``KbArticle.Statut`` (backend) : brouillon / publie / obsolete.
   Aucune valeur en dur ailleurs : la pastille et les helpers dérivent tous de
   cette carte unique.
   ========================================================================== */

export const KB_STATUT_MAP = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  publie: { label: 'Publié', tone: 'success' },
  obsolete: { label: 'Obsolète', tone: 'warning' },
}

export const StatutArticlePill = statusPill(KB_STATUT_MAP)

/** Libellé lisible d'un statut d'article (fallback = valeur brute). */
export function labelStatutArticle(statut) {
  return KB_STATUT_MAP[statut]?.label ?? statut ?? '—'
}

/** Découpe une chaîne de tags « a, b ; c » en liste propre, sans doublons. */
export function splitTags(tags) {
  if (!tags) return []
  const out = []
  const seen = new Set()
  for (const raw of String(tags).split(/[,;]/)) {
    const t = raw.trim()
    if (!t) continue
    const key = t.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push(t)
  }
  return out
}
