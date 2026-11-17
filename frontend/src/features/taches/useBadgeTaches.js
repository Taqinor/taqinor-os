import { useEffect, useState } from 'react'
import { lireAujourdhui, lireBadge } from '../../api/tachesApi'

/* ============================================================================
   TCH101 — Pastille de l'app Tâches. Deux nombres, jamais confondus :
     · `n` (GET taches/badge/, `badge.json`) = les tâches GARDÉES encore ouvertes d'Aujourd'hui
       (Essentiel, Prévu, Ce soir), jamais Proposé (A16-N5) ; peut valoir 0. C'est le chiffre
       posé sur l'icône de l'app installée : `navigator.setAppBadge(n)` s'il existe, sinon rien ;
       0 → `clearAppBadge()` (donnees.md inv. 11).
     · `aTrier` (`a_trier.boite_reception` d'Aujourd'hui) = la pastille de l'onglet « À trier »
       (masquée à 0) ; ses appelants : TCH124 (barre d'onglets) et la navigation de TCH131.
   Un cache de module partagé (60 s, une seule requête en vol) : plusieurs montages ne frappent
   pas deux fois le serveur. Un échec garde les derniers nombres connus (une pastille est un
   agrément, jamais une alarme) et le dit par `erreur`.
   Ce qu'iOS affiche réellement de `setAppBadge` n'est pas prouvé ici (liste « À essayer par Reda »).
   ========================================================================== */

const TTL_MS = 60_000

let cache = null // { expire, n, jour, aTrier }
let enVol = null
const ecouteurs = new Set()

/** Vide le cache partagé (tests, changement de compte). */
export function reinitialiserBadgeTaches() {
  cache = null
  enVol = null
}

/** Pose le nombre sur l'icône de l'app : rien si le navigateur n'a pas l'API, effacé à 0. */
export async function poserBadgeApp(n, nav = typeof navigator === 'undefined' ? null : navigator) {
  if (!nav) return false
  const valide = Number.isInteger(n) && n > 0
  const geste = valide ? nav.setAppBadge : nav.clearAppBadge
  if (typeof geste !== 'function') return false
  try {
    await (valide ? geste.call(nav, n) : geste.call(nav))
    return true
  } catch {
    // refus du navigateur (app non installée, permission) : la pastille de l'icône est un plus
    return false
  }
}

/** Lit les deux nombres du serveur, les garde en cache, pose la pastille de l'icône. */
export function chargerBadgeTaches({ force = false } = {}) {
  if (!force && cache && cache.expire > Date.now()) return Promise.resolve(cache)
  if (enVol) return enVol
  enVol = Promise.all([lireBadge(), lireAujourdhui()])
    .then(([badge, journee]) => {
      cache = {
        expire: Date.now() + TTL_MS,
        n: badge.data?.n ?? 0,
        jour: badge.data?.jour ?? null,
        aTrier: journee.data?.a_trier?.boite_reception ?? 0,
        erreur: false,
      }
      poserBadgeApp(cache.n)
      ecouteurs.forEach((fn) => fn(cache))
      return cache
    })
    .catch(() => {
      // garde les derniers nombres connus et signale l'échec ; la prochaine tentative est libre
      cache = { ...(cache ?? { n: 0, jour: null, aTrier: 0 }), expire: 0, erreur: true }
      ecouteurs.forEach((fn) => fn(cache))
      return cache
    })
    .finally(() => { enVol = null })
  return enVol
}

const VIDE = { n: 0, jour: null, aTrier: 0, erreur: false }

/**
 * `{ n, jour, aTrier, erreur }` : zéros tant que la réponse n'est pas là (jamais bloquant). Se
 * rafraîchit à l'arrivée sur l'écran, au retour au premier plan et à la reconnexion.
 * `actif: false` (compte sans Tâches) : aucune requête.
 */
export function useBadgeTaches({ actif = true } = {}) {
  const [etat, setEtat] = useState(() => cache ?? VIDE)

  useEffect(() => {
    if (!actif) return undefined
    ecouteurs.add(setEtat)
    chargerBadgeTaches()
    // au retour au premier plan : le cache de 60 s suffit ; à la reconnexion : relecture forcée
    const auPremierPlan = () => { if (document.visibilityState === 'visible') chargerBadgeTaches() }
    const aLaReconnexion = () => { chargerBadgeTaches({ force: true }) }
    document.addEventListener('visibilitychange', auPremierPlan)
    window.addEventListener('online', aLaReconnexion)
    return () => {
      ecouteurs.delete(setEtat)
      document.removeEventListener('visibilitychange', auPremierPlan)
      window.removeEventListener('online', aLaReconnexion)
    }
  }, [actif])

  return actif ? etat : VIDE
}

export default useBadgeTaches
