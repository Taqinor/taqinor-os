// APX15(d)/EZ16 — Message d'erreur FRANÇAIS, jamais du JSON brut.
//
// `lib/apiError.js` (VX203) est le contrat canonique pour une erreur AXIOS
// (`err.response.data`). Mais une bonne partie des écrans attrape le résultat
// d'un thunk Redux `unwrap()` : la valeur rejetée est alors le PAYLOAD DRF
// lui-même (`{detail: …}` / `{champ: […]}`), sans `response`. Les sites qui
// l'ignoraient retombaient sur `JSON.stringify(err)` — du jargon affiché tel
// quel à l'utilisateur (« {"client":["Ce champ est obligatoire."]} »).
//
// `frenchError` couvre les DEUX formes en un seul appel et ne renvoie JAMAIS
// autre chose qu'une phrase lisible.
import { getApiError } from './apiError.js'

export function frenchError(err, fallback = 'Une erreur est survenue. Réessayez.') {
  // Forme axios : le contrat canonique sait déjà tout faire.
  if (err?.response || err?.code === 'ECONNABORTED' || err?.message === 'Network Error') {
    return getApiError(err, fallback).message
  }
  // Forme « payload rejeté » (thunk unwrap) : on le présente au contrat
  // canonique comme s'il venait d'une réponse, pour n'avoir qu'UNE logique
  // d'extraction (detail > non_field_errors > première erreur de champ).
  if (err && typeof err === 'object') {
    return getApiError({ response: { data: err, headers: {} } }, fallback).message
  }
  if (typeof err === 'string' && err.trim()) return err
  return fallback
}

export default frenchError
