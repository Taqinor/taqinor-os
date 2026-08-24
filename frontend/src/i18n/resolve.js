// N93 — cœur PUR (zéro dépendance React, zéro import JSON) du cadre i18n
// léger : constantes + algorithme de résolution de clé. Les catalogues
// (fr/en/ar.json) sont injectés en paramètre plutôt qu'importés ici, pour que
// ce fichier reste chargeable tel quel par `node --test` (le glob CI
// `src/**/*.test.mjs`) SANS `node_modules/react` ni l'attribut d'import ESM
// `with { type: 'json' }` qu'exige `node --test` pour un `import … from
// '*.json'` direct — la même contrainte qui fait que `i18n-coverage.test.mjs`
// relit les catalogues via `readFileSync`+`JSON.parse` plutôt que de les
// importer. `context.js` (côté app, avec React) fournit les vrais catalogues
// (`./i18nCatalogs.js`) et ré-exporte `resolveValue` déjà lié à eux ; les
// tests peuvent charger LES MÊMES catalogues via `readFileSync` et appeler
// `resolveValueWithCatalogs` directement — c'est le MÊME algorithme, pas une
// réimplémentation.

export const LOCALES = ['fr', 'en', 'ar']
export const DEFAULT_LOCALE = 'fr'
export const STORAGE_KEY = 'taqinor.locale'

export function dirForLocale(locale) {
  return locale === 'ar' ? 'rtl' : 'ltr'
}

// Interpolation `{var}` : remplace chaque occurrence par vars[var] (ou laisse
// le token si la variable est absente, pour rester débogable).
export function interpolate(str, vars) {
  if (!vars || typeof str !== 'string') return str
  return str.replace(/\{(\w+)\}/g, (m, name) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : m)
}

export function readInitialLocale() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored && LOCALES.includes(stored)) return stored
  } catch { /* localStorage indisponible (SSR / navigation privée) */ }
  return DEFAULT_LOCALE
}

// Applique lang + dir sur <html> — appelé au montage ET à chaque changement.
export function applyDocumentAttrs(locale) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.lang = locale
  root.dir = dirForLocale(locale)
}

// N94 — résolution d'une valeur en fusionnant les SURCHARGES par-dessus les
// catalogues statiques N93. Chaîne de repli, dans l'ordre :
//   surcharge(locale courante) → statique(locale courante) → statique(FR) → repli.
// `overrides` a la forme `{ locale: { key: value } }` (ou est vide/undefined,
// auquel cas le comportement est EXACTEMENT celui du catalogue statique).
// `fallback` (optionnel) est ce qui doit s'afficher quand la clé n'existe dans
// AUCUN catalogue — un appelant qui connaît un libellé de repli fiable (ex. le
// `label:` FR d'une entrée de nav) le passe ici pour ne JAMAIS montrer la clé
// brute à l'écran ; sans `fallback` fourni, le comportement historique
// (retourner la clé, utile au débogage) est inchangé.
// `catalogs` = `{ fr: {...}, en: {...}, ar: {...} }`, injecté par l'appelant.
export function resolveValueWithCatalogs(key, locale, overrides, fallback, catalogs) {
  const ov = overrides || {}
  const ovLoc = ov[locale]
  if (ovLoc && Object.prototype.hasOwnProperty.call(ovLoc, key)) {
    const v = ovLoc[key]
    if (v != null) return v
  }
  const active = catalogs[locale] || catalogs[DEFAULT_LOCALE]
  let value = active[key]
  if (value == null) value = catalogs[DEFAULT_LOCALE][key]
  if (value == null) value = fallback !== undefined ? fallback : key
  return value
}
