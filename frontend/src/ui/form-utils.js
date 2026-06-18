/* G27 — Logique pure du système de formulaires (testable en .mjs).
   Validation par champ + croisée, état « dirty », résumé d'erreurs. Aucune
   dépendance React : les hooks/JSX vivent dans Form.jsx et useDirtyGuard.js. */

/** Champ vide ? (chaîne blanche, null, undefined, tableau vide). */
export function isEmptyValue(v) {
  if (v === null || v === undefined) return true
  if (typeof v === 'string') return v.trim() === ''
  if (Array.isArray(v)) return v.length === 0
  return false
}

/**
 * Valide un jeu de valeurs contre des règles.
 * `rules` = { champ: [ (value, allValues) => string|null, … ] }.
 * Une règle renvoie un message d'erreur (string) ou null si OK.
 * Renvoie `{ champ: message }` pour les seuls champs en erreur.
 */
export function runValidation(values, rules = {}) {
  const errors = {}
  for (const field of Object.keys(rules)) {
    const validators = rules[field] || []
    for (const validate of validators) {
      const msg = validate(values[field], values)
      if (msg) { errors[field] = msg; break } // 1ère erreur par champ
    }
  }
  return errors
}

/** Y a-t-il au moins une erreur ? */
export function hasErrors(errors) {
  return !!errors && Object.keys(errors).length > 0
}

/**
 * Résumé d'erreurs ordonné selon `fieldOrder` (les champs hors liste suivent
 * dans l'ordre d'apparition). Renvoie `[{ field, message }]`.
 */
export function errorSummary(errors, fieldOrder = []) {
  if (!errors) return []
  const keys = Object.keys(errors)
  const ordered = []
  for (const f of fieldOrder) if (keys.includes(f)) ordered.push(f)
  for (const f of keys) if (!ordered.includes(f)) ordered.push(f)
  return ordered.map((field) => ({ field, message: errors[field] }))
}

/** Comparaison structurelle stable (ordre des clés ignoré) pour l'état dirty. */
export function shallowEqualValues(a, b) {
  if (a === b) return true
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return false
  const ka = Object.keys(a)
  const kb = Object.keys(b)
  if (ka.length !== kb.length) return false
  for (const k of ka) {
    const va = a[k]
    const vb = b[k]
    if (Array.isArray(va) && Array.isArray(vb)) {
      if (va.length !== vb.length || va.some((x, i) => x !== vb[i])) return false
    } else if (va !== vb) {
      return false
    }
  }
  return true
}

/** Le formulaire est-il modifié par rapport à son état initial ? */
export function isDirty(initial, current) {
  return !shallowEqualValues(initial, current)
}

// ── Validateurs réutilisables (renvoient un message fr-FR ou null) ──────────

/** Champ obligatoire. */
export const required = (message = 'Ce champ est obligatoire.') => (v) =>
  isEmptyValue(v) ? message : null

/** Longueur minimale (chaînes). */
export const minLength = (n, message) => (v) =>
  typeof v === 'string' && v.trim().length > 0 && v.trim().length < n
    ? (message || `Au moins ${n} caractères.`)
    : null

/** E-mail simple (tolérant ; non vide requis ailleurs via `required`). */
export const email = (message = 'Adresse e-mail invalide.') => (v) =>
  isEmptyValue(v) || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(v)) ? null : message

/** Nombre dans un intervalle [min, max] (bornes incluses ; ignore le vide). */
export const numberInRange = (min, max, message) => (v) => {
  if (isEmptyValue(v)) return null
  const n = Number(String(v).replace(',', '.'))
  if (!Number.isFinite(n)) return message || 'Nombre invalide.'
  if (min != null && n < min) return message || `Minimum ${min}.`
  if (max != null && n > max) return message || `Maximum ${max}.`
  return null
}

/**
 * Validateur croisé : `b` doit valoir/dépasser `a` (utile pour les périodes).
 * À placer dans les règles du champ `bField`.
 */
export const atLeastField = (aField, message = 'Valeur incohérente.') =>
  (v, all) => {
    if (isEmptyValue(v) || isEmptyValue(all?.[aField])) return null
    return Number(v) >= Number(all[aField]) ? null : message
  }
