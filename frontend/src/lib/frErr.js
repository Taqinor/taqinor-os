// ENF19 — Message d'erreur FR d'une erreur serveur AXIOS (jamais de JSON brut).
// Trois variantes litterales que les ecrans Stock / Parametres recopiaient
// chacun : ordre de lecture identique, seule la profondeur differe.
//   frErrDetail  : string > detail
//   frErrChamps  : string > detail > premier message de champ
//   frErrForm    : string > detail > non_field_errors > premier message de champ
export function frErrDetail(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

export function frErrChamps(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  for (const v of Object.values(data)) {
    const m = Array.isArray(v) ? v[0] : v
    if (typeof m === 'string') return m
  }
  return fallback
}

export function frErrForm(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  if (Array.isArray(data.non_field_errors) && data.non_field_errors[0]) return data.non_field_errors[0]
  for (const v of Object.values(data)) {
    const m = Array.isArray(v) ? v[0] : v
    if (typeof m === 'string') return m
  }
  return fallback
}

/** Création rapide (modales « + Nouveau … ») : detail > premier message de
 *  champ (listes aplaties) > repli. Jamais de JSON brut. */
export function frErrRapide(err, fallback) {
  const data = err?.response?.data
  const detail = typeof data?.detail === 'string'
    ? data.detail
    : (data && typeof data === 'object'
      ? Object.values(data).flat().filter(Boolean)[0]
      : null)
  return typeof detail === 'string' ? detail : fallback
}
