import { useCallback, useState } from 'react'

/**
 * VX171 — useServerFieldErrors()
 *
 * DRF renvoie les erreurs de validation sous 3 formes possibles :
 *   - `{ champ: ['message'] }`     — le cas courant (liste de messages/champ) ;
 *   - `{ champ: 'message' }`       — un serializer qui renvoie une chaîne nue ;
 *   - `{ detail: 'message' }` / `{ non_field_errors: [...] }` ou une chaîne/
 *     array nue — pas de champ précis, ex. une 403/erreur métier globale.
 * `setFromResponse` normalise TOUJOURS vers `errors{champ: string}` — LA
 * source de vérité consommée par `FormField error=` (câblé, sous-consommé :
 * 12 fichiers seulement posaient `aria-invalid`, tout finissait en UN toast
 * opaque qui ne dit pas QUEL champ est en cause).
 *
 * `clearField(name)` doit être appelé dans chaque `set(field, value)` du
 * formulaire adoptant : sans ça, le rouge MENT pendant que l'utilisateur
 * corrige (il ne s'efface qu'au prochain submit, jamais à la frappe).
 *
 * Usage :
 *   const { errors, setFromResponse, clearField } = useServerFieldErrors()
 *   const set = (field, v) => { setFields(f => ({ ...f, [field]: v })); clearField(field) }
 *   ...catch (err) { setFromResponse(err?.response?.data) }
 *   <FormField error={errors.email}>...
 *
 * @returns {{
 *   errors: Record<string, string>,
 *   setErrors: (v: Record<string, string>) => void,
 *   setFromResponse: (data: unknown, opts?: { fallbackField?: string, fallback?: string }) => void,
 *   clearField: (field: string) => void,
 *   clearAll: () => void,
 * }}
 */
export function useServerFieldErrors() {
  const [errors, setErrors] = useState({})

  const setFromResponse = useCallback((data, opts = {}) => {
    const { fallbackField = 'submit', fallback = 'Une erreur est survenue.' } = opts

    // Réponse brute (chaîne, ou array non_field_errors) : aucun champ précis.
    if (data == null || typeof data !== 'object') {
      setErrors({ [fallbackField]: typeof data === 'string' && data ? data : fallback })
      return
    }
    if (Array.isArray(data)) {
      const first = data.find((v) => typeof v === 'string')
      setErrors({ [fallbackField]: first || fallback })
      return
    }

    const next = {}
    for (const [key, val] of Object.entries(data)) {
      // `detail`/`non_field_errors` = convention DRF pour une erreur SANS champ
      // précis (403, contrainte globale du serializer…) — jamais un vrai nom
      // de champ du formulaire, replié sur `fallbackField` plus bas.
      if (key === 'detail' || key === 'non_field_errors') continue
      if (Array.isArray(val)) {
        const first = val.find((v) => typeof v === 'string')
        if (first) next[key] = first
      } else if (typeof val === 'string') {
        next[key] = val
      }
    }
    // Rien d'exploitable par champ (ex. { detail: '…' } seul, ou 500 en clair)
    // → repli sur le champ générique, jamais une erreur silencieuse.
    if (Object.keys(next).length === 0) {
      const nonField = Array.isArray(data.non_field_errors) ? data.non_field_errors[0] : data.non_field_errors
      next[fallbackField] = data.detail || nonField || fallback
    }
    setErrors(next)
  }, [])

  const clearField = useCallback((field) => {
    setErrors((prev) => {
      if (!(field in prev)) return prev
      const next = { ...prev }
      delete next[field]
      return next
    })
  }, [])

  const clearAll = useCallback(() => setErrors({}), [])

  return { errors, setErrors, setFromResponse, clearField, clearAll }
}

export default useServerFieldErrors
