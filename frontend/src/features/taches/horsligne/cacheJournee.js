/* ============================================================================
   TCH100 — Cache de lecture d'Aujourd'hui, PAR COMPTE et PAR JOUR : clé `taches:aujourdhui:<user_id>:<jour>`
   (reference/api.md §5). Il sert à afficher « Hors ligne · dernière synchro à 15:02 » et à fournir le
   `lock_version` d'une tâche quand on la reporte hors ligne. Une seule journée est gardée par compte (la plus
   récente) ; tout est vidé à `taqinor:auth-logout` (poste partagé) — brancher une fois avec
   `viderCacheALaDeconnexion()`. Le stockage est un confort : refusé ou plein, on lit « rien » et on continue.
   Aucune horloge cachée : l'instant d'écriture est un argument.
   ========================================================================== */

export const PREFIXE_CACHE = 'taches:aujourdhui:'
export const EVENEMENT_DECONNEXION = 'taqinor:auth-logout'

export const cleCache = (userId, jour) => `${PREFIXE_CACHE}${userId}:${jour}`

function stockage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null // accès au stockage refusé (navigation privée stricte) : pas de cache
  }
}

function cles(magasin) {
  const toutes = []
  for (let i = 0; i < magasin.length; i += 1) toutes.push(magasin.key(i))
  return toutes.filter((c) => typeof c === 'string' && c.startsWith(PREFIXE_CACHE))
}

/** Garde la journée lue pour ce compte ; retire ses autres jours. `true` si le stockage l'a prise. */
export function ecrireJournee(userId, jour, donnees, maintenant = new Date()) {
  const magasin = stockage()
  if (!magasin || !Number.isInteger(userId)) return false
  try {
    const cle = cleCache(userId, jour)
    for (const autre of cles(magasin)) {
      if (autre.startsWith(`${PREFIXE_CACHE}${userId}:`) && autre !== cle) magasin.removeItem(autre)
    }
    magasin.setItem(cle, JSON.stringify({ ecrit_a: maintenant.toISOString(), donnees }))
    return true
  } catch {
    return false // plein ou refusé : l'écran marche sans cache
  }
}

/** `{ ecrit_a, donnees }` du compte pour ce jour, ou `null`. Jamais le cache d'un autre compte. */
export function lireJournee(userId, jour) {
  const magasin = stockage()
  if (!magasin) return null
  try {
    const brut = magasin.getItem(cleCache(userId, jour))
    return brut ? JSON.parse(brut) : null
  } catch {
    return null // contenu illisible : on le traite comme absent
  }
}

const deux = (n) => String(n).padStart(2, '0')

/** « 15:02 » : l'heure de la dernière lecture gardée pour ce compte, ou `null`. */
export function derniereSynchro(userId) {
  const magasin = stockage()
  if (!magasin) return null
  let recent = null
  for (const cle of cles(magasin)) {
    if (!cle.startsWith(`${PREFIXE_CACHE}${userId}:`)) continue
    try {
      const { ecrit_a: ecrit } = JSON.parse(magasin.getItem(cle))
      if (ecrit && (!recent || ecrit > recent)) recent = ecrit
    } catch {
      continue // entrée illisible : ignorée
    }
  }
  if (!recent) return null
  const d = new Date(recent)
  return Number.isNaN(d.getTime()) ? null : `${deux(d.getHours())}:${deux(d.getMinutes())}`
}

/** Vide le cache de TOUS les comptes. Rend le nombre d'entrées retirées. */
export function viderCache() {
  const magasin = stockage()
  if (!magasin) return 0
  const aRetirer = cles(magasin)
  for (const cle of aRetirer) {
    try {
      magasin.removeItem(cle)
    } catch {
      return 0 // le stockage refuse l'écriture : rien de plus à faire ici
    }
  }
  return aRetirer.length
}

/** Branche le vidage à la déconnexion ; rend la fonction de débranchement. */
export function viderCacheALaDeconnexion() {
  if (typeof window === 'undefined') return () => {}
  window.addEventListener(EVENEMENT_DECONNEXION, viderCache)
  return () => window.removeEventListener(EVENEMENT_DECONNEXION, viderCache)
}
