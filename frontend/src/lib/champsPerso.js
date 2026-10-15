// ENF19 — petits utilitaires des écrans « champs personnalisés » (Paramètres :
// Clients, Entreprise, Objets personnalisés). Un seul endroit — recopiés
// écran par écran, ils dérivaient.

/** Slug du code (clé JSON) : sans accents, minuscules, `_`, 50 caractères. */
export const slugifyCode = (s) => (s || '').trim().toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 50)

/** Message d'erreur serveur lisible (detail, ou première erreur de champ). */
export const erreurServeurLisible = (e, fallback) => {
  const d = e?.response?.data
  if (!d) return fallback
  if (typeof d === 'string') return d
  if (d.detail) return d.detail
  const first = Object.values(d)[0]
  return Array.isArray(first) ? first[0] : (first || fallback)
}
