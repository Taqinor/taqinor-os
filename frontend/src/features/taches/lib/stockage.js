/* ==========================================================================
   Le stockage local du module Tâches pour les BROUILLONS (le mot du bilan, la phrase de la saisie) : un seul
   endroit sait que le stockage du navigateur peut manquer (navigation privée stricte, plein, refusé) ; chaque
   appel rend une valeur sûre (`''`, `false`) et l'écran continue sans brouillon. Un préfixe enregistré par
   `viderALaDeconnexion` est vidé à `taqinor:auth-logout` : un poste partagé ne garde jamais le brouillon d'un
   autre compte. (Les caches hors ligne ont leur propre module : `horsligne/cacheJournee.js`, `cacheProjets.js`.)
   ========================================================================== */

export const EVENEMENT_DECONNEXION = 'taqinor:auth-logout'

function stockage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null // accès refusé (navigation privée stricte) : pas de brouillon
  }
}

/** Le texte gardé sous `cle`, ou `''` (clé absente, stockage indisponible). */
export function lireTexte(cle) {
  const s = stockage()
  if (!s || !cle) return ''
  try {
    return s.getItem(cle) ?? ''
  } catch {
    return '' // lecture refusée : traitée comme un brouillon vide
  }
}

/** Garde `texte` sous `cle` (vide : la clé est retirée) ; `false` si le stockage refuse — un confort, jamais une
 *  condition : la frappe reste à l'écran. */
export function ecrireTexte(cle, texte) {
  const s = stockage()
  if (!s || !cle) return false
  try {
    if (texte) s.setItem(cle, texte)
    else s.removeItem(cle)
    return true
  } catch {
    return false // plein ou refusé : rien n'est gardé au-delà de l'écran ouvert
  }
}

/** Retire toutes les clés qui commencent par `prefixe` ; rend le nombre retiré (0 si le stockage refuse). */
export function viderPrefixe(prefixe) {
  const s = stockage()
  if (!s) return 0
  try {
    const cles = []
    for (let i = 0; i < s.length; i += 1) {
      const cle = s.key(i)
      if (cle?.startsWith(prefixe)) cles.push(cle)
    }
    cles.forEach((cle) => s.removeItem(cle))
    return cles.length
  } catch {
    return 0 // le stockage refuse : rien à vider ici
  }
}

const PREFIXES_A_VIDER = new Set()

/** Inscrit `prefixe` au vidage de la déconnexion (une seule écoute pour tout le module, posée au premier appel). */
export function viderALaDeconnexion(prefixe) {
  if (typeof window === 'undefined') return
  if (PREFIXES_A_VIDER.size === 0) {
    window.addEventListener(EVENEMENT_DECONNEXION, () => { PREFIXES_A_VIDER.forEach(viderPrefixe) })
  }
  PREFIXES_A_VIDER.add(prefixe)
}
