/* ============================================================================
   PUB40 — Sélecteur de période + comparaison (logique PURE, sans JSX).
   ----------------------------------------------------------------------------
   Presets communs aux 4 écrans-données de la console (Dashboard/Cockpit/
   Campagnes/Journal) : hier / 7 derniers jours / 30 derniers jours /
   personnalisé, + calcul de la période de comparaison « vs période
   précédente » et le delta % associé. Colocalisé avec `DateRangeBar.jsx`
   (le composant CONTRÔLÉ qui utilise ces helpers) — ce fichier reste 100 %
   testable sans rendu React, à l'image d'`adsengine.js`.

   DOCTRINE (Done PUB40 — « hier vs même jour semaine passée ») : une période
   D'UN SEUL JOUR (preset « hier ») compare au MÊME JOUR de la semaine
   PRÉCÉDENTE (-7 j, contrôle l'effet jour-de-semaine) ; toute période plus
   longue (7j/30j/personnalisée) compare à la période équivalente
   IMMÉDIATEMENT précédente (period-over-period classique). Le backend
   (``metrics.previous_period``) applique EXACTEMENT la même règle — les deux
   DOIVENT rester en miroir.
   ========================================================================== */

export const DATE_RANGE_PRESETS = [
  { key: 'hier', label: 'Hier' },
  { key: '7j', label: '7 derniers jours' },
  { key: '30j', label: '30 derniers jours' },
  // FIXPUB2 — « Tout » : aucune borne (le backend renvoie tout l'historique
  // disponible). Devient le défaut de Cockpit/Campagnes/Journal (jamais de
  // Dashboard, qui garde 30j) — un fondateur qui ouvre la console ne doit
  // plus jamais se demander « pourquoi je ne vois pas cette ad d'il y a 2 mois ».
  { key: 'tout', label: 'Tout' },
  { key: 'personnalise', label: 'Personnalisé' },
]

// ``Date`` locale -> 'YYYY-MM-DD' (jamais l'UTC de `toISOString`, qui décale
// selon le fuseau — les bornes de date envoyées à l'API sont des dates
// CALENDAIRES, pas des instants).
export function toISODate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function addDays(date, days) {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  d.setDate(d.getDate() + days)
  return d
}

// Résout un preset en ``{debut, fin}`` (dates ISO, bornes INCLUSIVES) par
// rapport à ``today``. ``personnalise`` n'a pas de résolution automatique —
// renvoie ``null`` (l'écran garde les dates déjà saisies par l'utilisateur).
export function presetRange(presetKey, today = new Date()) {
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  switch (presetKey) {
    case 'hier': {
      const y = addDays(t, -1)
      return { debut: toISODate(y), fin: toISODate(y) }
    }
    case '7j':
      return { debut: toISODate(addDays(t, -6)), fin: toISODate(t) }
    case '30j':
      return { debut: toISODate(addDays(t, -29)), fin: toISODate(t) }
    // FIXPUB2 — « Tout » résout des bornes VIDES (jamais `null`, contrairement
    // à `personnalise` : `DateRangeBar.selectPreset` déréférence directement
    // `resolved.debut`/`resolved.fin`) — le repli `debut/fin || undefined`
    // déjà présent dans chaque écran envoie alors une requête SANS bornes.
    case 'tout':
      return { debut: '', fin: '' }
    default:
      return null
  }
}

function parseISODate(value) {
  if (!value || typeof value !== 'string') return null
  const [y, m, d] = value.split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

// Nombre de jours INCLUS dans ``[debut, fin]`` (1 pour un jour unique) ;
// ``null`` si les bornes sont absentes/invalides.
export function rangeLengthDays({ debut, fin } = {}) {
  const start = parseISODate(debut)
  const end = parseISODate(fin)
  if (!start || !end) return null
  return Math.round((end - start) / 86400000) + 1
}

// Période de comparaison PUB40 (voir doctrine en tête de fichier). ``null``
// si la période courante n'est pas résolue.
export function previousRange({ debut, fin } = {}) {
  const start = parseISODate(debut)
  const end = parseISODate(fin)
  if (!start || !end) return null
  const length = Math.round((end - start) / 86400000) + 1
  const shiftDays = length <= 1 ? 7 : length
  return {
    debut: toISODate(addDays(start, -shiftDays)),
    fin: toISODate(addDays(end, -shiftDays)),
  }
}

// Delta courant vs précédent : ``{delta, pct, direction}``. ``pct`` reste
// ``null`` (jamais un 0/Infinity fabriqué) si l'un des deux nombres manque ou
// si le précédent est nul (division impossible). Les deux entrées peuvent
// être des strings numériques (montants Decimal sérialisés par l'API).
export function computeDelta(current, previous) {
  const cur = current === null || current === undefined ? null : Number(current)
  const prev = previous === null || previous === undefined ? null : Number(previous)
  if (cur === null || prev === null || !Number.isFinite(cur) || !Number.isFinite(prev)) {
    return { delta: null, pct: null, direction: 'flat' }
  }
  const delta = cur - prev
  const pct = prev !== 0 ? (delta / Math.abs(prev)) * 100 : null
  return {
    delta,
    pct,
    direction: delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat',
  }
}

// Formatte un delta % avec signe explicite (jamais un « 0 % » quand la
// donnée manque — « — » à la place). ``pct`` est déjà en points de pourcent
// (ex. 12.3, pas 0.123).
export function formatDeltaPct(pct) {
  if (pct === null || pct === undefined || !Number.isFinite(pct)) return '—'
  const rounded = Math.round(pct * 10) / 10
  const sign = rounded > 0 ? '+' : rounded < 0 ? '−' : '±'
  return `${sign}${Math.abs(rounded)} %`
}
