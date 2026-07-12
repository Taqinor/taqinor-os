// VX203 — Contrat d'erreur UNIQUE : point d'extraction CANONIQUE pour les
// erreurs axios/DRF, promu hors de `lib/toast.js` (qui délègue désormais
// ici). Avant : 259 sites re-implémentaient chacun une version PARTIELLE de
// cette extraction (souvent juste `err?.response?.data?.detail`), ratant les
// formes `non_field_errors`/erreurs par champ/429/500 HTML/timeout — chacune
// avec son propre message générique divergent. `getApiError()` couvre TOUTES
// ces formes en un seul endroit ; les nouveaux appels doivent l'importer au
// lieu de ré-extraire `.response?.data?.detail` à la main.
//
// Code en anglais, textes utilisateur en français. Aucun import React ici :
// appelable depuis n'importe où (handlers, thunks, axios, formulaires).

/**
 * getApiError(error, fallback?) → { message, fieldErrors? }
 *   message     : chaîne FR lisible, JAMAIS du JSON/HTML brut.
 *   fieldErrors : { [champ]: premier message } si le payload DRF porte des
 *                 erreurs PAR CHAMP (hors `detail`/`non_field_errors`) —
 *                 `undefined` sinon, pour que les formulaires puissent
 *                 mapper un message par champ sans re-parser la réponse.
 */
export function getApiError(error, fallback = 'Une erreur est survenue.') {
  // VX55 — timeout (axios ECONNABORTED) : distinct d'une annulation
  // volontaire (gérée séparément par l'appelant via AbortController).
  if (error?.code === 'ECONNABORTED') {
    return { message: 'La connexion a expiré. Vérifiez votre connexion et réessayez.' }
  }
  if (error?.message === 'Network Error') {
    return { message: 'Impossible de contacter le serveur. Vérifiez votre connexion.' }
  }

  const status = error?.response?.status
  if (status === 429) {
    return { message: 'Trop de requêtes — patientez un instant avant de réessayer.' }
  }

  const data = error?.response?.data
  const contentType = error?.response?.headers?.['content-type'] ?? ''
  // 500 (ou autre) renvoyé en HTML brut (page d'erreur Django DEBUG, proxy,
  // gateway timeout) — ne JAMAIS l'afficher tel quel dans un toast.
  if (typeof data === 'string' && (contentType.includes('text/html') || /^\s*<!DOCTYPE/i.test(data))) {
    return {
      message: status >= 500
        ? 'Erreur serveur. Réessayez ou contactez le support si le problème persiste.'
        : fallback,
    }
  }
  if (typeof data === 'string' && data.trim()) {
    return { message: data }
  }

  if (data && typeof data === 'object') {
    if (typeof data.detail === 'string' && data.detail.trim()) {
      return { message: data.detail, fieldErrors: fieldErrorsFrom(data) }
    }
    if (Array.isArray(data.non_field_errors) && data.non_field_errors.length) {
      return { message: String(data.non_field_errors[0]), fieldErrors: fieldErrorsFrom(data) }
    }
    const fieldErrors = fieldErrorsFrom(data)
    if (fieldErrors) {
      const firstKey = Object.keys(fieldErrors)[0]
      return { message: fieldErrors[firstKey], fieldErrors }
    }
  }

  if (status >= 500) {
    return { message: 'Erreur serveur. Réessayez ou contactez le support si le problème persiste.' }
  }
  return { message: fallback }
}

// Construit `{champ: premier message}` depuis un payload DRF `{champ: [...]}`
// — ignore `detail`/`non_field_errors` (déjà traités comme message global).
function fieldErrorsFrom(data) {
  const out = {}
  let found = false
  for (const [key, v] of Object.entries(data)) {
    if (key === 'detail' || key === 'non_field_errors') continue
    if (Array.isArray(v) && v.length) { out[key] = String(v[0]); found = true }
    else if (typeof v === 'string' && v.trim()) { out[key] = v; found = true }
  }
  return found ? out : undefined
}

/** Compat message-seul — utilisé par le contrat toast global (`lib/toast.js`). */
export function apiErrorMessage(error, fallback) {
  return getApiError(error, fallback).message
}
