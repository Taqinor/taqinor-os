/* ============================================================================
   ACAL25 (C-ACAL-034) — UNE SEULE FONCTION DE SURFACE DE POSE POUR TERRAIN ET
   OMBRIÈRE.
   ----------------------------------------------------------------------------
   Constat : `documentTerrain` (champ au sol) persistait le module, mais
   `documentOmbriere` non — ni `moduleLongM`/`moduleCourtM`/`moduleWc`/
   `modulesParTable`, ni l'allée : à la réouverture, ces champs revenaient vides
   et « Générer le devis » composait au repli 550 W / kWc 0. Le correctif de
   `documentTerrain` (ERR-QAH-CALEPINAGE-SOL-MODULE-NON-PERSISTE) n'avait pas
   été généralisé. Deux copies divergentes d'un même aller-retour.

   Ce module est l'UNIQUE aller-retour saisie ⇄ surface persistée :
   * `documentSurfacePose(saisie, reponse, kind)` — la surface (`poseSurfaces[]`,
     contrat `roof_layout_v2.schema.json $defs.poseSurface`) ;
   * `saisieDepuisSurface(surface)` — la saisie d'ORIGINE, relue d'une surface ;
   * `reponseDepuisSurface(surface)` — le plan du moteur déjà calculé, réaffiché
     sans être refait.
   Tout ce qui vient du moteur est recopié tel quel sous `engine` ; rien n'y est
   recalculé. Persister puis rouvrir puis persister sans toucher à rien rend
   la MÊME surface, octet pour octet.

   Les fonctions pures de mesure (`nombre`, `pasMesure`, `tauxOccupation`,
   `contourTerrain`…) vivent ICI — `ModeTerrain.jsx` les ré-exporte.
   ========================================================================== */

/** Une saisie numérique, ou `null` — jamais un 0 de remplacement. */
export function nombre(brut) {
  if (brut === null || brut === undefined || brut === '') return null
  const v = Number(brut)
  return Number.isFinite(v) ? v : null
}

/**
 * CAL89 — le PAS INTER-RANGÉES, MESURÉ sur les rangées que le moteur a posées.
 * Le plus petit écart entre deux `y0` consécutifs distincts. Moins de deux
 * rangées ⇒ `null` : non mesurable, et on ne le remplace pas.
 */
export function pasMesure(rangees) {
  const y = Array.from(
    new Set((rangees ?? [])
      .map((r) => Number(r?.y0))
      .filter((v) => Number.isFinite(v))),
  ).sort((a, b) => a - b)
  if (y.length < 2) return null
  let min = Infinity
  for (let i = 1; i < y.length; i += 1) min = Math.min(min, y[i] - y[i - 1])
  return Number.isFinite(min) && min > 0 ? min : null
}

/** Emprise totale (m²) des tables RENDUES par le moteur. */
export function empriseTablesM2(tables) {
  return (tables ?? []).reduce((acc, t) => {
    const l = Math.abs(Number(t?.x1) - Number(t?.x0))
    const p = Math.abs(Number(t?.y1) - Number(t?.y0))
    return Number.isFinite(l) && Number.isFinite(p) ? acc + l * p : acc
  }, 0)
}

/**
 * CAL89 — le TAUX D'OCCUPATION DU SOL (GCR), une SORTIE : emprises des tables
 * du moteur ÷ surface du terrain. L'un des deux termes manque ⇒ `null`.
 */
export function tauxOccupation(tables, aireTerrainM2) {
  const aire = nombre(aireTerrainM2)
  if (aire === null || aire <= 0) return null
  const emprise = empriseTablesM2(tables)
  if (!emprise) return null
  return emprise / aire
}

/** Le contour métrique du terrain, depuis les dimensions SAISIES. */
export function contourTerrain(largeurM, profondeurM) {
  const l = nombre(largeurM)
  const p = nombre(profondeurM)
  if (l === null || p === null || l <= 0 || p <= 0) return null
  return [[0, 0], [l, 0], [l, p], [0, p]]
}

export const KIND_SOL = 'sol'
export const KIND_OMBRIERE = 'ombriere'

const PAR_DEFAUT = {
  [KIND_SOL]: { repere: 'TERRAIN', label: 'Champ au sol' },
  [KIND_OMBRIERE]: { repere: 'OMBRIERE', label: 'Ombrière' },
}

/**
 * Les clés de saisie qui ENTRENT dans la demande du moteur : qu'une seule
 * change et le plan calculé ne correspond plus à la saisie. `flowAzimuthDeg`
 * (ombrière) est l'azimut d'empilement envoyé au moteur.
 */
export const CLES_ENTREE_MOTEUR = [
  'largeurM', 'profondeurM', 'rowAzimuthDeg', 'flowAzimuthDeg', 'tiltDeg',
  'moduleLongM', 'moduleCourtM', 'puissanceWc', 'modulesParTable', 'alleeM',
]

/** `true` si changer le champ `cle` rend le plan du moteur périmé. */
export function entreeMoteurChangee(cle) {
  return CLES_ENTREE_MOTEUR.includes(cle)
}

/** Le bloc `engine` : tout ce que le moteur a rendu, recopié sans calcul. */
function blocMoteur(reponse, aire) {
  const plan = (reponse?.plans ?? [])[0] ?? null
  const tables = plan?.tables ?? []
  return {
    modules: Number.isFinite(Number(plan?.modules)) ? Number(plan.modules) : null,
    // Un plan RELU n'a plus ses rangées : le pas mesuré à l'enregistrement
    // revient par `_pasRecharge` (jamais recalculé, jamais perdu).
    rowPitchM: pasMesure(plan?.rangees) ?? reponse?._pasRecharge ?? null,
    tables,
    groundCoverageRatio: tauxOccupation(tables, aire),
    versionMoteur: reponse?.version_moteur ?? null,
    hashEntree: reponse?.hash_entree ?? null,
  }
}

/**
 * La surface de pose PERSISTÉE (`poseSurfaces[]`), pour un champ au sol
 * (`kind: 'sol'`) ou une ombrière (`kind: 'ombriere'`). Aucune clé de
 * structure, de charge ni de prix : le contrat n'en déclare aucune.
 */
export function documentSurfacePose(saisie, reponse, kind) {
  const defauts = PAR_DEFAUT[kind] ?? PAR_DEFAUT[KIND_SOL]
  const contour = contourTerrain(saisie.largeurM, saisie.profondeurM)
  const aire = contour ? nombre(saisie.largeurM) * nombre(saisie.profondeurM) : null
  const module = {
    moduleLongM: nombre(saisie.moduleLongM),
    moduleCourtM: nombre(saisie.moduleCourtM),
    moduleWc: nombre(saisie.puissanceWc),
    modulesParTable: nombre(saisie.modulesParTable),
    alleeM: nombre(saisie.alleeM),
  }
  const engine = blocMoteur(reponse, aire)
  if (kind === KIND_OMBRIERE) {
    return {
      kind,
      id: saisie.repere || defauts.repere,
      label: saisie.label || defauts.label,
      buildingId: saisie.buildingId || '',
      contourM: contour ?? [],
      areaM2: aire,
      tiltDeg: nombre(saisie.tiltDeg),
      clearHeightM: nombre(saisie.clearHeightM),
      flowAzimuthDeg: nombre(saisie.flowAzimuthDeg),
      rowAzimuthDeg: nombre(saisie.flowAzimuthDeg),
      ...module,
      engine,
    }
  }
  return {
    kind: KIND_SOL,
    id: saisie.repere || defauts.repere,
    label: saisie.label || defauts.label,
    contourM: contour ?? [],
    areaM2: aire,
    terrainSlopeDeg: nombre(saisie.penteTerrainDeg),
    rowAzimuthDeg: nombre(saisie.rowAzimuthDeg),
    tiltDeg: nombre(saisie.tiltDeg),
    ...module,
    engine,
  }
}

const texte = (v) => (v === null || v === undefined ? undefined : String(v))

/**
 * La saisie d'ORIGINE relue d'une surface persistée (champs texte des
 * formulaires). Une valeur absente de la surface n'apparaît PAS dans le
 * résultat : la saisie courante reste, jamais écrasée par un « vide ».
 */
export function saisieDepuisSurface(surface) {
  const s = surface ?? {}
  const contour = Array.isArray(s.contourM) ? s.contourM : []
  const brut = {
    repere: s.id,
    label: s.label,
    buildingId: s.buildingId,
    largeurM: contour.length === 4 ? texte(contour[1]?.[0]) : undefined,
    profondeurM: contour.length === 4 ? texte(contour[2]?.[1]) : undefined,
    penteTerrainDeg: texte(s.terrainSlopeDeg),
    rowAzimuthDeg: s.kind === KIND_OMBRIERE ? undefined : texte(s.rowAzimuthDeg),
    flowAzimuthDeg: texte(s.flowAzimuthDeg),
    clearHeightM: texte(s.clearHeightM),
    tiltDeg: texte(s.tiltDeg),
    moduleLongM: texte(s.moduleLongM),
    moduleCourtM: texte(s.moduleCourtM),
    puissanceWc: texte(s.moduleWc),
    modulesParTable: texte(s.modulesParTable),
    alleeM: texte(s.alleeM),
  }
  const saisie = {}
  for (const [cle, valeur] of Object.entries(brut)) {
    if (valeur !== undefined) saisie[cle] = valeur
  }
  return saisie
}

/** Le plan du moteur RELU d'une surface : réaffiché tel quel, jamais refait. */
export function reponseDepuisSurface(surface) {
  const engine = surface?.engine ?? {}
  return {
    plans: [{ modules: engine.modules ?? null, tables: engine.tables ?? [] }],
    version_moteur: engine.versionMoteur ?? null,
    hash_entree: engine.hashEntree ?? null,
    _pasRecharge: engine.rowPitchM ?? null,
  }
}

/** Les surfaces d'un genre, dans l'ordre du document. */
export function surfacesDuGenre(surfaces, kind) {
  return (Array.isArray(surfaces) ? surfaces : []).filter((s) => s?.kind === kind)
}

/**
 * Remplace la surface de MÊME genre et de MÊME id (à sa place, l'ordre du
 * document ne bouge pas) ; sinon l'ajoute en fin. Les autres surfaces — d'un
 * autre genre ou d'un autre id — ne sont JAMAIS touchées.
 */
export function remplacerSurface(surfaces, surface) {
  const liste = Array.isArray(surfaces) ? surfaces : []
  const rang = liste.findIndex((s) => s?.kind === surface.kind && (s?.id ?? '') === surface.id)
  if (rang < 0) return [...liste, surface]
  return liste.map((s, i) => (i === rang ? surface : s))
}

/** La liste SANS la surface (genre + id) ; le reste est rendu tel quel. */
export function retirerSurface(surfaces, kind, id) {
  return (Array.isArray(surfaces) ? surfaces : [])
    .filter((s) => !(s?.kind === kind && (s?.id ?? '') === id))
}

/** Un repère libre pour une NOUVELLE surface du genre (`TERRAIN`, `TERRAIN-2`…). */
export function repereLibre(surfaces, kind) {
  const base = (PAR_DEFAUT[kind] ?? PAR_DEFAUT[KIND_SOL]).repere
  const pris = new Set(surfacesDuGenre(surfaces, kind).map((s) => s.id))
  if (!pris.has(base)) return base
  for (let n = 2; ; n += 1) {
    if (!pris.has(`${base}-${n}`)) return `${base}-${n}`
  }
}
