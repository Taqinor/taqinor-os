// Origine d'API depuis une variable d'environnement Vite.
// Règle de prod : variable VIDE = même origine que la page (chemins relatifs
// via nginx). Ne JAMAIS faire new URL('') — c'est ce qui faisait s'écrouler
// la page Paramètres en production (TypeError: Invalid URL).
export function originFrom(viteUrl) {
  const v = (viteUrl || '').trim()
  if (!v) return ''
  try {
    return new URL(v).origin
  } catch {
    return ''
  }
}
