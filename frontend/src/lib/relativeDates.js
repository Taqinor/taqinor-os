// NTUX4 — Filtres relatifs de date. Module PUR (aucun import React) :
// `resolveRelativeRange(preset)` résout un preset EN BORNES ABSOLUES
// {debut, fin} (objets Date, bornes inclusives) au moment de l'APPEL — jamais
// persisté comme dates absolues dans `SavedView.configuration` (NTUX1). Une
// vue sauvegardée avec « ce trimestre » réévalue donc le trimestre COURANT à
// chaque chargement, pas celui de la date de sauvegarde.

export const RELATIVE_DATE_PRESETS = [
  { id: 'today', label: "Aujourd'hui" },
  { id: 'this_week', label: 'Cette semaine' },
  { id: 'this_month', label: 'Ce mois' },
  { id: 'this_quarter', label: 'Ce trimestre' },
  { id: 'this_year', label: 'Cette année' },
  { id: 'last_7_days', label: '7 derniers jours' },
  { id: 'last_30_days', label: '30 derniers jours' },
  { id: 'last_90_days', label: '90 derniers jours' },
  { id: 'last_month', label: 'Mois dernier' },
]

function startOfDay(d) {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}
function endOfDay(d) {
  const x = new Date(d)
  x.setHours(23, 59, 59, 999)
  return x
}
function addDays(d, n) {
  const x = new Date(d)
  x.setDate(x.getDate() + n)
  return x
}

/**
 * resolveRelativeRange(preset, now = new Date()) → { debut: Date, fin: Date }
 * `now` est injectable pour les tests (jamais lu implicitement autrement
 * qu'au moment de l'appel — RÉÉVALUÉ à chaque rendu, jamais mis en cache).
 * Preset inconnu → null (l'appelant traite comme « aucun filtre »).
 */
export function resolveRelativeRange(preset, now = new Date()) {
  const today = startOfDay(now)
  switch (preset) {
    case 'today':
      return { debut: today, fin: endOfDay(now) }
    case 'this_week': {
      // Semaine ISO : lundi → dimanche.
      const day = (today.getDay() + 6) % 7 // 0 = lundi
      const debut = addDays(today, -day)
      return { debut, fin: endOfDay(addDays(debut, 6)) }
    }
    case 'this_month': {
      const debut = new Date(today.getFullYear(), today.getMonth(), 1)
      const fin = endOfDay(new Date(today.getFullYear(), today.getMonth() + 1, 0))
      return { debut, fin }
    }
    case 'this_quarter': {
      const q = Math.floor(today.getMonth() / 3)
      const debut = new Date(today.getFullYear(), q * 3, 1)
      const fin = endOfDay(new Date(today.getFullYear(), q * 3 + 3, 0))
      return { debut, fin }
    }
    case 'this_year': {
      const debut = new Date(today.getFullYear(), 0, 1)
      const fin = endOfDay(new Date(today.getFullYear(), 11, 31))
      return { debut, fin }
    }
    case 'last_7_days':
      return { debut: startOfDay(addDays(today, -6)), fin: endOfDay(now) }
    case 'last_30_days':
      return { debut: startOfDay(addDays(today, -29)), fin: endOfDay(now) }
    case 'last_90_days':
      return { debut: startOfDay(addDays(today, -89)), fin: endOfDay(now) }
    case 'last_month': {
      const debut = new Date(today.getFullYear(), today.getMonth() - 1, 1)
      const fin = endOfDay(new Date(today.getFullYear(), today.getMonth(), 0))
      return { debut, fin }
    }
    default:
      return null
  }
}
