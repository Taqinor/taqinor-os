/* ============================================================================
   R2-070 — Cache de lecture des écrans PROJETS, PAR COMPTE : clé `taches:projets:<user_id>:<clé>` (`liste` pour la
   liste des projets, `projet-<id>` pour la vue d'un projet). Même mécanisme que `cacheJournee.js` (qu'il ne modifie
   pas) : le dernier état LU du serveur sert hors ligne, au lieu d'un faux « Aucun projet » ; vidé à
   `taqinor:auth-logout` (poste partagé) ; le stockage est un confort — refusé ou plein, on lit « rien » et on continue.
   Aucune horloge cachée : l'instant d'écriture est un argument.
   ========================================================================== */

export const PREFIXE_CACHE_PROJETS = 'taches:projets:'
const EVENEMENT_DECONNEXION = 'taqinor:auth-logout'

export const cleCacheProjets = (userId, cle) => `${PREFIXE_CACHE_PROJETS}${userId}:${cle}`

function stockage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null // accès refusé (navigation privée stricte) : pas de cache
  }
}

/** Garde ce qui vient d'être lu pour ce compte. `true` si le stockage l'a pris. */
export function ecrireProjetsCache(userId, cle, donnees, maintenant = new Date()) {
  const magasin = stockage()
  if (!magasin || !Number.isInteger(userId)) return false
  try {
    magasin.setItem(cleCacheProjets(userId, cle), JSON.stringify({ ecrit_a: maintenant.toISOString(), donnees }))
    return true
  } catch {
    return false // plein ou refusé : l'écran marche sans cache
  }
}

/** `{ ecrit_a, donnees }` du compte pour cette clé, ou `null`. Jamais le cache d'un autre compte. */
export function lireProjetsCache(userId, cle) {
  const magasin = stockage()
  if (!magasin || !Number.isInteger(userId)) return null
  try {
    const brut = magasin.getItem(cleCacheProjets(userId, cle))
    return brut ? JSON.parse(brut) : null
  } catch {
    return null // contenu illisible : traité comme absent
  }
}

/** Vide le cache de TOUS les comptes. Rend le nombre d'entrées retirées. */
export function viderCacheProjets() {
  const magasin = stockage()
  if (!magasin) return 0
  const cles = []
  for (let i = 0; i < magasin.length; i += 1) {
    const c = magasin.key(i)
    if (typeof c === 'string' && c.startsWith(PREFIXE_CACHE_PROJETS)) cles.push(c)
  }
  try {
    for (const c of cles) magasin.removeItem(c)
  } catch {
    return 0 // le stockage refuse : rien de plus à faire ici
  }
  return cles.length
}

/** Branche le vidage à la déconnexion ; rend la fonction de débranchement. */
export function viderCacheProjetsALaDeconnexion() {
  if (typeof window === 'undefined') return () => {}
  window.addEventListener(EVENEMENT_DECONNEXION, viderCacheProjets)
  return () => window.removeEventListener(EVENEMENT_DECONNEXION, viderCacheProjets)
}
