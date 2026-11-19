import { useEffect, useState } from 'react'
import { lireAujourdhui, lireBadge } from '../../api/tachesApi'
import { EVENEMENT_CREEES } from './lib/fiche'

/* ============================================================================
   TCH101 — Pastille de l'app Tâches. Deux nombres, jamais confondus :
     · `n` (GET taches/badge/, `badge.json`) = les tâches GARDÉES encore ouvertes d'Aujourd'hui
       (Essentiel, Prévu, Ce soir), jamais Proposé (A16-N5) ; peut valoir 0. C'est le chiffre
       posé sur l'icône de l'app installée : `navigator.setAppBadge(n)` s'il existe, sinon rien ;
       0 → `clearAppBadge()` (donnees.md inv. 11).
     · `aTrier` (`a_trier` de `badge/`, F3 ; à défaut `a_trier.boite_reception` d'Aujourd'hui, une
       seconde requête) = la pastille de l'onglet « À trier »
       (masquée à 0) ; ses appelants : TCH124 (barre d'onglets) et la navigation de TCH131.
   Un cache de module partagé (60 s, une seule requête en vol) : plusieurs montages ne frappent
   pas deux fois le serveur. Un échec garde les derniers nombres connus (une pastille est un
   agrément, jamais une alarme) et le dit par `erreur`.
   Ce qu'iOS affiche réellement de `setAppBadge` n'est pas prouvé ici (liste « À essayer par Reda »).
   ========================================================================== */

const TTL_MS = 60_000

let cache = null // { expire, n, jour, aTrier }
let enVol = null
let suivante = null // R2-024 : la relecture forcée qui attend la fin de la lecture en vol
const ecouteurs = new Set()

/** Vide le cache partagé (tests, changement de compte). */
export function reinitialiserBadgeTaches() {
  cache = null
  enVol = null
  suivante = null
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

/** Une lecture : une seule requête quand `badge/` porte `a_trier` ; sinon (serveur plus ancien) l'ancien chemin. */
function lancer() {
  enVol = lireBadge()
    .then(async (badge) => {
      const direct = badge.data?.a_trier
      const journee = Number.isInteger(direct) ? null : await lireAujourdhui()
      return [badge, journee, direct]
    })
    .then(([badge, journee, direct]) => {
      cache = {
        expire: Date.now() + TTL_MS,
        n: badge.data?.n ?? 0,
        jour: badge.data?.jour ?? null,
        aTrier: journee ? (journee.data?.a_trier?.boite_reception ?? 0) : direct,
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

/** Lit les deux nombres du serveur, les garde en cache, pose la pastille de l'icône. `force` : un geste vient de les
 *  changer — la lecture déjà en vol est partie AVANT lui, donc la relecture forcée se met derrière elle (R2-024). */
export function chargerBadgeTaches({ force = false } = {}) {
  if (!force && cache && cache.expire > Date.now()) return Promise.resolve(cache)
  if (!enVol) return lancer()
  if (!force) return enVol
  if (!suivante) suivante = enVol.then(() => { suivante = null; return enVol ?? lancer() })
  return suivante
}

/** Corrige TOUT DE SUITE la pastille d'À trier d'un geste qui vient de partir (une carte rangée = −1) ; la relecture
 *  forcée qui suit la confirme ou la corrige. Sans lecture préalable, rien n'est inventé. */
export function ajusterBadgeATrier(delta) {
  if (!cache || !Number.isFinite(delta)) return
  cache = { ...cache, aTrier: Math.max(0, (cache.aTrier ?? 0) + delta) }
  ecouteurs.forEach((fn) => fn(cache))
}

const VIDE = { n: 0, jour: null, aTrier: 0, erreur: false }

/**
 * `{ n, jour, aTrier, erreur }` : zéros tant que la réponse n'est pas là (jamais bloquant). Se
 * rafraîchit à l'arrivée sur l'écran, au retour au premier plan, à la reconnexion et après une création.
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
    // R2-024 : une création (saisie, collage, file rejouée) change le compte d'À trier, sur n'importe quel écran
    const apresCreation = () => { chargerBadgeTaches({ force: true }) }
    document.addEventListener('visibilitychange', auPremierPlan)
    window.addEventListener('online', aLaReconnexion)
    window.addEventListener(EVENEMENT_CREEES, apresCreation)
    return () => {
      ecouteurs.delete(setEtat)
      document.removeEventListener('visibilitychange', auPremierPlan)
      window.removeEventListener('online', aLaReconnexion)
      window.removeEventListener(EVENEMENT_CREEES, apresCreation)
    }
  }, [actif])

  return actif ? etat : VIDE
}

export default useBadgeTaches
