/**
 * CALX121 — LA COUPE TRANSVERSALE D'UNE RANGÉE SUR L'AUTRE : logique PURE.
 * ----------------------------------------------------------------------------
 * Constat de la tâche : le pas inter-rangées est déjà calculé par la géométrie
 * solaire (`apps/web/src/lib/roofPro2.ts:320-346`) puis vérifié par lancer de
 * rayons (`apps/web/src/scripts/roofPro11/scene3d.ts:1959-2008`,
 * `publishRowPitch`), mais le résultat n'est qu'un TEXTE — rien ne dessine la
 * coupe. Ce module ne repave rien et n'invente aucune géométrie : il MESURE le
 * pas sur les panneaux DÉJÀ POSÉS du document (`roof_layout` v2,
 * `zone.geometry.panels`), exactement comme `pasInterRangeeMesure`
 * (`scene3d.ts:2514`, « le plus petit écart entre deux rangées distinctes »)
 * et `pasMesure` (`ModeTerrain.jsx`) le font déjà pour leurs propres jeux de
 * données — aucune seconde formule de pas n'est introduite ici.
 *
 * DEUX CONSTANTES PHYSIQUES DU MODULE (720 Wc, le même produit posé partout
 * dans le dépôt — `PANEL2_SHORT_M`/`FRONT_STRUT_M` de `roofPro2.ts`) sont
 * dupliquées ci-dessous, pour la même raison que `horizonMath.js` et
 * `obstructionMath.js` juste à côté : `frontend/vitest.config.js` (hors
 * périmètre de cette lane) ne déclare pas l'alias `@rooflib`/le plugin de
 * transpilation TS du builder, donc un import statique de
 * `apps/web/src/lib/roofPro2.ts` échouerait dès la résolution du module sous
 * Vitest. Elles servent UNIQUEMENT à dessiner l'empreinte et la hauteur du
 * module déjà posé — le pas lui-même reste toujours MESURÉ, jamais recalculé
 * à partir d'elles.
 *
 * LE RAYON SOLAIRE DE CONCEPTION est obtenu par un vrai IMPORT (pas une
 * copie) de `sunPosition` (`./horizonMath.js`, elle-même la formule exacte de
 * `apps/web/src/lib/roofPro2.ts sunDirection`) à midi solaire au solstice
 * d'hiver — la même hypothèse que `describeRowPitch` affiche déjà en texte.
 *
 * ZÉRO CHIFFRE INVENTÉ. Un pan sans panneaux posés, ou avec moins de deux
 * rangées distinctes, n'a pas de pas mesurable : la coupe n'est PAS dessinée,
 * et le motif exact est renvoyé (jamais un pas de remplacement).
 */

import { sunPosition, JOUR_SOLSTICE_HIVER } from './horizonMath.js'

const DEG2RAD = Math.PI / 180

/** Petit côté du module 720 Wc (m, dans le sens de la pente) — même valeur que
 *  `PANEL2_SHORT_M` de `apps/web/src/lib/roofPro2.ts`. */
export const PROFONDEUR_MODULE_M = 1.303

/** Hauteur du montant avant (bas) du châssis lesté (m) — même valeur que
 *  `FRONT_STRUT_M` de `apps/web/src/lib/roofPro2.ts`. Sans objet en pose
 *  affleurante (pas de châssis). */
export const MONTANT_AVANT_M = 0.1

/** Heure solaire de conception (midi) — même hypothèse que `describeRowPitch`. */
export const HEURE_CONCEPTION = 12

/**
 * Le pas inter-rangées MESURÉ sur les panneaux déjà posés (m, centre à centre),
 * projetés sur l'axe d'empilement des rangées (perpendiculaire aux rangées,
 * donné par l'azimut de pose). On prend le plus petit écart entre deux
 * projections consécutives DISTINCTES — même principe que
 * `pasInterRangeeMesure` (`scene3d.ts`). Moins de deux rangées distinctes, ou
 * azimut absent, ⇒ `null` (non mesurable), jamais une valeur de remplacement.
 */
export function pasRangeeMesure(panels, azimuthDeg) {
  if (!Array.isArray(panels) || panels.length < 2 || !Number.isFinite(azimuthDeg)) return null
  const azRad = azimuthDeg * DEG2RAD
  // Direction d'empilement des rangées (celle que vise le pan) — même
  // convention que `layoutProRows2` (`s = [sin(az), cos(az)]`).
  const sx = Math.sin(azRad)
  const sy = Math.cos(azRad)
  const projections = panels
    .filter((p) => Number.isFinite(p?.cx) && Number.isFinite(p?.cy))
    .map((p) => p.cx * sx + p.cy * sy)
  if (projections.length < 2) return null
  // Arrondi au millimètre pour regrouper les panneaux d'une MÊME rangée (le
  // placement peut porter un bruit flottant infime) sans jamais fusionner deux
  // rangées réellement distinctes.
  const v = Array.from(new Set(projections.map((p) => Math.round(p * 1000) / 1000))).sort((a, b) => a - b)
  if (v.length < 2) return null
  let min = Infinity
  for (let i = 1; i < v.length; i++) min = Math.min(min, v[i] - v[i - 1])
  return Number.isFinite(min) && min > 0 ? min : null
}

/**
 * La coupe transversale de deux rangées consécutives du pan actif, ou l'état
 * « non calculée » avec son motif exact. `zone` est l'entrée `zones[]` du
 * document `roof_layout` v2 (`zone.geometry`, posée par `serializeLayout`) ;
 * `latitudeDeg` vient de `layout.pin.lat` — AUCUNE des deux n'est devinée.
 */
export function construireCoupe({ zone, latitudeDeg } = {}) {
  const geometrie = zone?.geometry ?? null
  if (!geometrie) {
    return { disponible: false, motif: 'Ce pan n’a encore aucune géométrie posée : la coupe n’est pas calculée.' }
  }
  const tiltDeg = Number.isFinite(geometrie.tiltDeg) ? geometrie.tiltDeg : null
  if (tiltDeg === null) {
    return { disponible: false, motif: 'L’inclinaison posée est absente du document : la coupe n’est pas calculée.' }
  }
  const rowPitchM = pasRangeeMesure(geometrie.panels, geometrie.azimuthDeg)
  if (rowPitchM === null) {
    return {
      disponible: false,
      motif: 'Moins de deux rangées posées sur ce pan : le pas n’est pas mesurable, la coupe n’est pas calculée.',
    }
  }
  if (!Number.isFinite(latitudeDeg)) {
    return {
      disponible: false,
      motif: 'Latitude du site inconnue (aucun repère posé) : le rayon solaire de conception n’est pas calculable.',
    }
  }

  const flush = !!geometrie.flush
  const tiltRad = tiltDeg * DEG2RAD
  const riseM = PROFONDEUR_MODULE_M * Math.sin(tiltRad)
  const depthFootprintM = PROFONDEUR_MODULE_M * Math.cos(tiltRad)
  // Pose affleurante (toit en pente) : pas de châssis, le module épouse la
  // pente — aucune hauteur hors-tout distincte du toit lui-même.
  const hauteurHorsToutM = flush ? null : MONTANT_AVANT_M + riseM

  const soleil = sunPosition(latitudeDeg, JOUR_SOLSTICE_HIVER, HEURE_CONCEPTION)
  const rayonSolaireDeg = soleil.elevationDeg
  // Rangées jointives (affleurant), ou soleil sous l'horizon au midi de
  // conception (latitude extrême) : aucun espacement anti-ombrage à dessiner.
  const longueurOmbreM = flush || rayonSolaireDeg <= 0 ? 0 : riseM / Math.tan(rayonSolaireDeg * DEG2RAD)

  return {
    disponible: true,
    tiltDeg,
    flush,
    family: geometrie.family ?? null,
    rowPitchM,
    depthFootprintM,
    riseM,
    hauteurHorsToutM,
    rayonSolaireDeg,
    longueurOmbreM,
  }
}
