// ODY10 — Badges vivants de la grille d'apps (l'accueil respire).
// ----------------------------------------------------------------------------
// UN SEUL appel réseau, agrégé côté serveur : l'endpoint fédéré ARC40 EXISTANT
// `GET /reporting/reports/kpi-federes/?format=badges` (les providers sont
// déclarés par chaque app dans son `platform.py`, collectés par
// `core/platform.py`, gating ModuleToggle inclus). On ne ré-agrège JAMAIS à la
// main côté client, et on n'interroge jamais une app en particulier.
//
// Trois garanties tenues ici :
//   • JAMAIS BLOQUANT — le hook rend `{}` immédiatement ; la grille est
//     peinte d'abord, les badges arrivent ensuite. Aucun état « chargement »
//     n'est exposé : il n'y a rien à faire attendre.
//   • CACHE COURT partagé par le module (60 s) : revenir sur l'accueil après
//     être entré dans une app ne redéclenche pas un appel.
//   • ÉCHEC SILENCIEUX — un badge est un agrément, pas une information dont
//     l'absence doit alarmer : une erreur réseau laisse simplement la grille
//     sans compteurs.
import { useEffect, useState } from 'react'
import reportingApi from '../../api/reportingApi'

const TTL_MS = 60_000

// Cache module (par onglet) : { expire, badges } + la requête en vol, pour que
// deux montages rapprochés partagent le MÊME appel.
let cache = null
let enVol = null

/** Vide le cache — utilisé par les tests et par un changement de société. */
export function _resetBadgeCache() {
  cache = null
  enVol = null
}

/** Normalise la réponse en `{ [cleApp]: {valeur, label, unite?} }`. */
export function indexerBadges(payload) {
  const liste = Array.isArray(payload?.badges) ? payload.badges : []
  const out = {}
  liste.forEach((b) => {
    if (!b?.app || typeof b.valeur !== 'number') return
    out[b.app] = { valeur: b.valeur, label: b.label || '', unite: b.unite || '' }
  })
  return out
}

/** chargerBadges — un seul appel en vol, résultat mis en cache TTL_MS. */
export function chargerBadges() {
  const maintenant = Date.now()
  if (cache && cache.expire > maintenant) return Promise.resolve(cache.badges)
  if (enVol) return enVol
  enVol = reportingApi.kpiBadges()
    .then((res) => {
      const badges = indexerBadges(res?.data)
      cache = { expire: Date.now() + TTL_MS, badges }
      return badges
    })
    .catch(() => ({})) // agrément, jamais une alarme
    .finally(() => { enVol = null })
  return enVol
}

/**
 * useAppBadges — `{ [cleApp]: {valeur, label, unite} }`, vide tant que la
 * réponse n'est pas là. Ne bloque JAMAIS le rendu de la grille.
 */
export function useAppBadges() {
  const [badges, setBadges] = useState(() => cache?.badges ?? {})

  useEffect(() => {
    let vivant = true
    chargerBadges().then((valeurs) => { if (vivant) setBadges(valeurs) })
    return () => { vivant = false }
  }, [])

  return badges
}

export default useAppBadges
