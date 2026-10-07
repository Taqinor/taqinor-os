// ACAL201 — les fichiers du calepinage (photos de site, plan importé, aperçu)
// sont servis par un proxy Django en CHEMIN RELATIF (même origine, cookie de
// session httpOnly : aucun jeton à injecter). Une image chargée par <img> ou
// `new Image()` ne passe pas par axios : l'URL doit donc porter elle-même
// l'origine d'API (VITE_API_URL ; vide = même origine, chemin laissé tel quel).
import { originFrom } from './origin'

export function urlFichierCalepinage(url, viteUrl = import.meta.env.VITE_API_URL) {
  if (typeof url !== 'string' || !url) return url
  // Déjà absolue (https:, http:, data:, blob:) : jamais préfixée.
  if (/^[a-z][a-z0-9+.-]*:/i.test(url) || url.startsWith('//')) return url
  const origine = originFrom(viteUrl)
  if (!origine) return url
  return `${origine}${url.startsWith('/') ? '' : '/'}${url}`
}

// Le cookie de session part avec l'image : « anonymous » ne l'envoie qu'en
// MÊME origine ; une origine d'API distincte exige « use-credentials ».
export function crossOriginFichierCalepinage(viteUrl = import.meta.env.VITE_API_URL) {
  return originFrom(viteUrl) ? 'use-credentials' : 'anonymous'
}
