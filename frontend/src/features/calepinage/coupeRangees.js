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
 * LE MODULE ET LE SOLEIL NE SONT PLUS DES CONSTANTES (ACAL255). La montée et
 * l'empreinte se dessinent au PETIT CÔTÉ du module RÉEL du pan
 * (`zone.geometry.moduleId` → `modules[]` du document, cotes lues par
 * `moduleSelect.cotesPourPan`) ; un pan sans module désigné, ou dont le module
 * n'a pas de cotes, n'a PAS de coupe (« module non renseigné ») — jamais
 * 1,303 m supposé. Le soleil est celui du DIMENSIONNEMENT réellement appliqué
 * par le moteur de pas V2 : `estimatorBrainV2.DESIGN_SOLAR_HOUR` (10 h solaire)
 * au solstice d'hiver, la projection et le plancher de 5° étant ceux de son
 * `shadeLengthM` (parité vérifiée contre `rowPitchM` dans les tests). Le pas
 * lui-même reste toujours MESURÉ, jamais recalculé.
 *
 * ZÉRO CHIFFRE INVENTÉ. Un pan sans panneaux posés, ou avec moins de deux
 * rangées distinctes, n'a pas de pas mesurable : la coupe n'est PAS dessinée,
 * et le motif exact est renvoyé (jamais un pas de remplacement).
 */

import { DESIGN_SOLAR_HOUR, sunPositionWinterSolstice } from '@rooflib/estimatorBrainV2'
import { FRONT_STRUT_M } from '@rooflib/roofPro2'
import { cotesPourPan } from '@roofpro/moduleSelect'

const DEG2RAD = Math.PI / 180
/** Plancher d'élévation du moteur V2 (`shadeLengthM`) : soleil très bas → 5°. */
const ELEVATION_PLANCHER_DEG = 5

/** Motif quand aucun module n'est désigné sur le pan (jamais un module supposé). */
export const MOTIF_MODULE_NON_RENSEIGNE = (
  'Module non renseigné sur ce pan : choisissez le module du pan, la coupe '
  + 'n’est pas calculée (aucune cote de module supposée).'
)

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
 * `latitudeDeg` vient de `layout.pin.lat`, `modules` est le catalogue `modules[]`
 * de la racine du document — AUCUN des trois n'est deviné.
 */
export function construireCoupe({ zone, latitudeDeg, modules } = {}) {
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

  // ACAL255 — le module RÉEL du pan : jamais un petit côté supposé.
  const moduleId = typeof geometrie.moduleId === 'string' ? geometrie.moduleId.trim() : ''
  if (!moduleId) return { disponible: false, motif: MOTIF_MODULE_NON_RENSEIGNE }
  const cotes = cotesPourPan(Array.isArray(modules) ? modules : [], moduleId)
  if (!Number.isFinite(cotes?.courtM)) {
    return {
      disponible: false,
      motif: cotes?.message ?? MOTIF_MODULE_NON_RENSEIGNE,
    }
  }
  const profondeurModuleM = cotes.courtM

  const flush = !!geometrie.flush
  const tiltRad = tiltDeg * DEG2RAD
  const riseM = profondeurModuleM * Math.sin(tiltRad)
  const depthFootprintM = profondeurModuleM * Math.cos(tiltRad)
  // Pose affleurante (toit en pente) : pas de châssis, le module épouse la
  // pente — aucune hauteur hors-tout distincte du toit lui-même.
  const hauteurHorsToutM = flush ? null : FRONT_STRUT_M + riseM

  // Le soleil de DIMENSIONNEMENT du moteur V2 (10 h solaire, solstice d'hiver).
  const soleil = sunPositionWinterSolstice(latitudeDeg, DESIGN_SOLAR_HOUR)
  const rayonSolaireDeg = soleil.elevationDeg
  // Rangées jointives (affleurant) : aucun espacement anti-ombrage à dessiner.
  // Sinon la longueur d'ombre de `estimatorBrainV2.shadeLengthM` (rangées plein
  // sud : projection |cos γ|, élévation plancher 5°).
  const longueurOmbreM = flush
    ? 0
    : Math.max(0, (riseM * Math.abs(Math.cos(soleil.azimuthFromSouthDeg * DEG2RAD)))
      / Math.tan(Math.max(ELEVATION_PLANCHER_DEG, rayonSolaireDeg) * DEG2RAD))

  return {
    disponible: true,
    tiltDeg,
    flush,
    family: geometrie.family ?? null,
    rowPitchM,
    profondeurModuleM,
    montantAvantM: FRONT_STRUT_M,
    heureConceptionH: DESIGN_SOLAR_HOUR,
    depthFootprintM,
    riseM,
    hauteurHorsToutM,
    rayonSolaireDeg,
    longueurOmbreM,
  }
}
