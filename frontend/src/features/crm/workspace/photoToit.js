/* VT13 (fondateur 10/09/2026) — LA PHOTO RÉELLE DU TOIT, SOUS LE TRACÉ.
   ---------------------------------------------------------------------------
   La visite terrain assemble les photos du toit (VT9) puis le commercial CALE
   l'image sur la carte par ses 4 coins (VT11). VT12 sert le résultat sur le
   LEAD (`GET /crm/leads/<id>/photo-toit/` → {visite_id, url, texture_calage}).
   Ce module prépare le drapage de cette image dans le MÊME repère de dessin
   que le contour du toit (`traceToit.dessinerContour`) : l'atelier 3D et la
   fiche lead affichent donc la photo EXACTEMENT sous le tracé, jamais à côté.

   RIEN N'EST INVENTÉ : une charge sans url, sans calage, ou dont les 4 coins
   ne sont pas des coordonnées plausibles rend `null` — l'écran n'affiche alors
   aucune photo (jamais une image approximative « à peu près posée »).

   AUCUNE DEUXIÈME PROJECTION : quand un contour existe, les coins passent par
   SON `projeter` (traceToit.js). Sans contour, le module bâtit un cadre depuis
   les 4 coins seuls, avec les MÊMES primitives de repère que l'atelier AO. */
import {
  ORDRE_LATLNG, creerRepere, lngLatVersMetres,
// Extension EXPLICITE : ces modules sont chargés tels quels par `node --test`.
} from '../../ao/toiture/repere.js'
import { COTE_DESSIN } from './traceToit.js'

const borne = (v, min, max) => Number.isFinite(v) && v >= min && v <= max

/** Les 4 coins bruts du calage → `[[lat, lng] × 4]`, sinon `null`. */
export function normaliserCoins(brut) {
  if (!Array.isArray(brut) || brut.length !== 4) return null
  const coins = []
  for (const coin of brut) {
    if (!Array.isArray(coin) || coin.length < 2) return null
    const lat = Number(coin[0])
    const lng = Number(coin[1])
    if (!borne(lat, -90, 90) || !borne(lng, -180, 180)) return null
    coins.push([lat, lng])
  }
  return coins
}

/**
 * La charge servie par `GET /crm/leads/<id>/photo-toit/` → `{visiteId, url,
 * coins}` exploitable, ou `null`.
 *
 * La forme du serveur est TOUJOURS `{visite_id, url, texture_calage}` (contrat
 * `apps/crm/contract_samples/lead_photo_toit.json`) : ses trois clés sont
 * nulles quand il n'y a rien à montrer — ce n'est pas une erreur, c'est
 * l'absence, et elle se traduit ici par un simple `null`.
 */
export function normaliserTextureToit(charge) {
  if (!charge || typeof charge !== 'object') return null
  const url = typeof charge.url === 'string' ? charge.url.trim() : ''
  const coins = normaliserCoins(charge.texture_calage?.coins)
  if (!url || !coins) return null
  return { visiteId: charge.visite_id ?? null, url, coins }
}

/**
 * Cadre de dessin des 4 coins SEULS (aucun contour client à suivre) : mêmes
 * unités que `dessinerContour` (côté maximal = COTE_DESSIN, nord en haut).
 */
function cadreDepuisCoins(coins) {
  let repere
  let metres
  try {
    repere = creerRepere({ origine_lnglat: [coins[0][1], coins[0][0]] })
    metres = coins.map((c) => lngLatVersMetres(repere, c, ORDRE_LATLNG))
  } catch {
    return null
  }
  const xs = metres.map((m) => m.x)
  const ys = metres.map((m) => m.y)
  if (![...xs, ...ys].every(Number.isFinite)) return null
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const etendue = Math.max(maxX - minX, maxY - minY)
  if (!Number.isFinite(etendue) || etendue <= 0) return null
  const echelle = COTE_DESSIN / etendue
  return {
    quad: metres.map((m) => [(m.x - minX) * echelle, (maxY - m.y) * echelle]),
    largeur: Math.max(1, Number(((maxX - minX) * echelle).toFixed(1))),
    hauteur: Math.max(1, Number(((maxY - minY) * echelle).toFixed(1))),
  }
}

/**
 * `{quad, largeur, hauteur}` — le quadrilatère de destination où draper la
 * photo, dans les unités de viewBox du dessin, ou `null` si rien n'est
 * drapable.
 *
 * `dessin` (le retour de `dessinerContour`, éventuellement `null`) commande :
 * quand il existe, la photo se cale dans SON repère — donc sous SON contour ;
 * sinon les 4 coins définissent leur propre cadre.
 */
export function quadPhotoToit(dessin, coins) {
  const propres = normaliserCoins(coins)
  if (!propres) return null
  if (dessin && typeof dessin.projeter === 'function') {
    const quad = propres.map(([lat, lng]) => dessin.projeter(lat, lng))
    if (quad.some((point) => point == null)) return null
    return { quad, largeur: dessin.largeur, hauteur: dessin.hauteur }
  }
  return cadreDepuisCoins(propres)
}
