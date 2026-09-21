/* ============================================================================
   UX39 — Géométrie PURE du diagramme de Gantt (sans JSX, sans dépendance).
   ----------------------------------------------------------------------------
   Convertit des plages de dates (tâches, phases, jalons) en offsets/largeurs en
   pourcentage sur une échelle temporelle commune. Aucune bibliothèque Gantt :
   ces fonctions pilotent un rendu CSS/SVG léger. Testées unitairement.
   ========================================================================== */

const MS_PER_DAY = 24 * 60 * 60 * 1000

/** Parse une date ISO (YYYY-MM-DD) ou Date en Date, sinon null. */
export function parseDate(value) {
  if (!value) return null
  const d = value instanceof Date ? value : new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Nombre de jours (entier, ≥ 0) entre deux dates inclusives (fin − début + 1). */
export function daysBetween(start, end) {
  const a = parseDate(start)
  const b = parseDate(end)
  if (!a || !b) return 0
  const diff = Math.round((b.getTime() - a.getTime()) / MS_PER_DAY)
  return diff < 0 ? 0 : diff
}

/**
 * Bornes temporelles [min, max] couvrant toutes les barres.
 * `bars` : [{ date_debut, date_fin }]. Retourne { min: Date, max: Date } ou
 * null si aucune date exploitable.
 */
export function timelineBounds(bars = []) {
  let min = null
  let max = null
  for (const b of bars) {
    const d = parseDate(b.date_debut ?? b.debut ?? b.date_debut_prevue)
    const f = parseDate(b.date_fin ?? b.fin ?? b.date_fin_prevue) || d
    if (d && (!min || d < min)) min = d
    const end = f || d
    if (end && (!max || end > max)) max = end
  }
  if (!min || !max) return null
  // Au moins un jour d'amplitude pour éviter une division par zéro.
  if (max <= min) max = new Date(min.getTime() + MS_PER_DAY)
  return { min, max }
}

/**
 * Position d'UNE barre sur l'échelle [min, max], en POURCENTAGE.
 * Retourne { offsetPct, widthPct } bornés à [0, 100].
 *   offsetPct : distance du bord gauche (début de la plage) depuis `min`.
 *   widthPct  : largeur de la plage (≥ une valeur plancher lisible).
 */
export function barGeometry(debut, fin, min, max, { minWidthPct = 1.5 } = {}) {
  const a = parseDate(debut)
  const lo = parseDate(min)
  const hi = parseDate(max)
  if (!a || !lo || !hi || hi <= lo) return { offsetPct: 0, widthPct: 0 }
  const b = parseDate(fin) || a
  const totalMs = hi.getTime() - lo.getTime()

  const startMs = Math.max(0, a.getTime() - lo.getTime())
  const endMs = Math.min(totalMs, Math.max(startMs, b.getTime() - lo.getTime()))

  let offsetPct = (startMs / totalMs) * 100
  let widthPct = ((endMs - startMs) / totalMs) * 100
  if (widthPct < minWidthPct) widthPct = minWidthPct
  if (offsetPct < 0) offsetPct = 0
  if (offsetPct > 100) offsetPct = 100
  if (offsetPct + widthPct > 100) widthPct = Math.max(0, 100 - offsetPct)
  return { offsetPct, widthPct }
}

/**
 * Position PONCTUELLE (jalon) sur l'échelle [min, max], en pourcentage.
 * Retourne { leftPct } borné à [0, 100], ou null si date invalide.
 */
export function markerGeometry(date, min, max) {
  const d = parseDate(date)
  const lo = parseDate(min)
  const hi = parseDate(max)
  if (!d || !lo || !hi || hi <= lo) return null
  const total = hi.getTime() - lo.getTime()
  let leftPct = ((d.getTime() - lo.getTime()) / total) * 100
  if (leftPct < 0) leftPct = 0
  if (leftPct > 100) leftPct = 100
  return { leftPct }
}

/**
 * Prépare des barres pour le rendu : chaque item reçoit sa géométrie calculée
 * sur des bornes communes. `accessors` mappe les champs de date d'un item.
 * Retourne { bounds, rows: [{ ...item, geometry }] }.
 */
export function layoutGantt(items = [], {
  debutKey = 'date_debut_prevue',
  finKey = 'date_fin_prevue',
} = {}) {
  const bars = items.map((it) => ({
    date_debut: it[debutKey],
    date_fin: it[finKey],
  }))
  const bounds = timelineBounds(bars)
  if (!bounds) return { bounds: null, rows: items.map((it) => ({ ...it, geometry: null })) }
  const rows = items.map((it) => ({
    ...it,
    geometry: barGeometry(it[debutKey], it[finKey], bounds.min, bounds.max),
  }))
  return { bounds, rows }
}
