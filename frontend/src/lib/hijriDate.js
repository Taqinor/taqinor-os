/* ============================================================================
   NTI18N12 — Conversion d'AFFICHAGE grégorien → hégirien.
   ----------------------------------------------------------------------------
   Lib PURE JS, AUCUNE dépendance ajoutée : s'appuie sur le calendrier
   islamique NATIF d'`Intl` (extension Unicode `u-ca-islamic-umalqura` —
   calendrier hégirien officiel le plus largement reconnu), déjà embarqué
   dans tout navigateur/moteur JS moderne (données ICU) — zéro implémentation
   maison d'algorithme de conversion (source d'erreurs notoire, cf. NTI18N14
   qui exclut explicitement tout calcul algorithmique pour les FÊTES
   religieuses officielles — ceci est un AFFICHAGE secondaire, pas une date
   légale).

   AFFICHAGE SEUL : ces fonctions ne calculent et ne renvoient JAMAIS rien qui
   soit stocké — jamais en remplacement de la date grégorienne, toujours EN
   PLUS d'elle (règle NTI18N12).
   ========================================================================== */

// Locale FR + calendrier hégirien : rend les noms de mois en transcription
// française usuelle (« ramadan », « chaabane »…) plutôt qu'en écriture
// arabe — cohérent avec l'exemple de l'énoncé (« 12 Ramadan 1447 »).
const HIJRI_LOCALE_TAG = 'fr-u-ca-islamic-umalqura'

function toDate(value) {
  // Garde falsy AVANT construction : `new Date(null)` vaut l'epoch
  // (1970-01-01, PAS une date invalide) — sans ce garde, `formatHijriDate
  // (null)` renverrait une vraie date au lieu de `null`.
  if (!value) return null
  const d = value instanceof Date ? value : new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s
}

/**
 * Date hégirienne SEULE : « 26 Ramadan 1447 » (jour, mois capitalisé, année).
 * `null` si `value` n'est pas une date valide (jamais d'exception).
 */
export function formatHijriDate(value) {
  const d = toDate(value)
  if (!d) return null
  const parts = new Intl.DateTimeFormat(HIJRI_LOCALE_TAG, {
    day: 'numeric', month: 'long', year: 'numeric',
  }).formatToParts(d)
  const get = (type) => parts.find((p) => p.type === type)?.value
  const day = get('day')
  const month = get('month')
  const year = get('year')
  if (!day || !month || !year) return null
  return `${day} ${capitalize(month)} ${year}`
}

/**
 * Date hégirienne + grégorienne EN PLUS (jamais en remplacement) :
 * « 26 Ramadan 1447 (2026-03-15) » — format de l'exemple d'acceptation
 * NTI18N12. `null` si `value` n'est pas une date valide : l'appelant garde
 * alors simplement la date grégorienne déjà affichée par ailleurs (aucune
 * régression visuelle possible).
 */
export function formatWithHijri(value) {
  const d = toDate(value)
  if (!d) return null
  const hijri = formatHijriDate(d)
  if (!hijri) return null
  const iso = d.toISOString().slice(0, 10)
  return `${hijri} (${iso})`
}

/**
 * Vrai UNIQUEMENT quand les DEUX conditions de l'énoncé sont réunies : la
 * langue d'interface est l'arabe ET la préférence utilisateur est active.
 * Centralise la garde pour que chaque écran consommateur applique EXACTEMENT
 * la même règle (jamais une variante qui affiche l'hégirien en FR/EN, jamais
 * une variante qui l'affiche sans préférence explicite).
 */
export function shouldShowHijri({ locale, calendrierHegirien }) {
  return locale === 'ar' && calendrierHegirien === true
}
