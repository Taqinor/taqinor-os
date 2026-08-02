/* AOF88 — Vocabulaire pur des OBSTACLES : repères lettrés, natures, dégagement.
   ----------------------------------------------------------------------------
   Trois règles qui doivent tenir sans écran, donc testables hors React (c'est le
   fichier que `degagement.test.mjs` interroge) :

   1. REPÈRE LETTRÉ SANS COLLISION. Sur une planche, un obstacle s'appelle A, B,
      C… et deux obstacles qui portent la même lettre rendent le relevé
      inexploitable — on ne sait plus de quel édicule parle la question posée au
      client. `prochainRepere` rend TOUJOURS la plus petite lettre libre : après
      une suppression, la lettre libérée est reprise, jamais dupliquée.

   2. TREIZE NATURES NOMMÉES. Un « obstacle » générique force chaque écran à
      réinventer son rendu et son dégagement ; les treize natures du relevé sont
      donc énumérées ici, une fois.

   3. DÉGAGEMENT DÉRIVÉ DE LA PROVENANCE. Un obstacle MESURÉ se contourne à
      0,30 m ; un obstacle vu sur plan, à confirmer ou deviné se contourne à
      0,50 m — parce que son emprise réelle est incertaine et qu'une rangée
      posée au ras d'un édicule mal placé est une rangée à redéposer. La
      surcharge manuelle reste possible, mais elle est SIGNALÉE (`surcharge`) :
      un dégagement réduit à la main doit se voir. */

/* ── 1. Repères lettrés ─────────────────────────────────────────────────────── */

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

/** Index 0 → « A », 25 → « Z », 26 → « AA » (numérotation type tableur). */
export function repereDepuisIndex(index) {
  let i = Math.trunc(Number(index))
  if (!Number.isFinite(i) || i < 0) return 'A'
  let out = ''
  do {
    out = ALPHABET[i % 26] + out
    i = Math.floor(i / 26) - 1
  } while (i >= 0)
  return out
}

/** « A » → 0, « AA » → 26. Rend `null` si ce n'est pas un repère lettré. */
export function indexDepuisRepere(repere) {
  const r = String(repere ?? '').toUpperCase()
  if (!/^[A-Z]+$/.test(r)) return null
  let n = 0
  for (const c of r) n = n * 26 + (ALPHABET.indexOf(c) + 1)
  return n - 1
}

/**
 * La plus petite lettre LIBRE. Après suppression de B parmi A, B, C, le
 * prochain obstacle reprend B — les repères restent denses et jamais dupliqués.
 */
export function prochainRepere(existants = []) {
  const pris = new Set(
    (existants || [])
      .map((o) => (typeof o === 'string' ? o : o?.repere))
      .map((r) => String(r ?? '').toUpperCase())
      .filter((r) => r.length > 0),
  )
  for (let i = 0; i < 100000; i += 1) {
    const candidat = repereDepuisIndex(i)
    if (!pris.has(candidat)) return candidat
  }
  return repereDepuisIndex(pris.size)
}

/** Renumérote séquentiellement (A, B, C…) dans l'ordre courant de la liste. */
export function renumeroter(obstacles = []) {
  return obstacles.map((o, i) => ({ ...o, repere: repereDepuisIndex(i) }))
}

/** Repères présents plus d'une fois — doit TOUJOURS être vide. */
export function reperesEnDouble(obstacles = []) {
  const vus = new Map()
  for (const o of obstacles) {
    const r = String(o?.repere ?? '').toUpperCase()
    vus.set(r, (vus.get(r) ?? 0) + 1)
  }
  return [...vus.entries()].filter(([, n]) => n > 1).map(([r]) => r)
}

/* ── 2. Les treize natures ──────────────────────────────────────────────────── */

export const NATURES_OBSTACLE = [
  { cle: 'edicule', libelle: 'Édicule technique', forme: 'surface' },
  { cle: 'cage_escalier', libelle: "Cage d'escalier", forme: 'surface' },
  { cle: 'cheminee', libelle: 'Cheminée', forme: 'surface' },
  { cle: 'lanterneau', libelle: 'Lanterneau', forme: 'surface' },
  { cle: 'exutoire', libelle: 'Exutoire de fumée', forme: 'surface' },
  { cle: 'climatisation', libelle: 'Groupe de climatisation', forme: 'surface' },
  { cle: 'gaine', libelle: 'Gaine / conduit', forme: 'surface' },
  { cle: 'antenne', libelle: 'Antenne / mât', forme: 'surface' },
  { cle: 'trappe', libelle: "Trappe d'accès", forme: 'surface' },
  { cle: 'reservation', libelle: 'Réservation / percement', forme: 'surface' },
  { cle: 'acrotere', libelle: 'Acrotère', forme: 'lineaire' },
  { cle: 'joint_dilatation', libelle: 'Joint de dilatation', forme: 'lineaire' },
  { cle: 'muret', libelle: 'Muret', forme: 'lineaire' },
]

export function natureParCle(cle) {
  return NATURES_OBSTACLE.find((n) => n.cle === cle) ?? null
}

/** Une nature linéaire (muret, joint, acrotère) se dessine comme une épaisseur. */
export function estLineaire(cle) {
  return natureParCle(cle)?.forme === 'lineaire'
}

/* ── 3. Dégagement dérivé de la provenance ──────────────────────────────────── */

export const DEGAGEMENT_MESURE_M = 0.3
export const DEGAGEMENT_INCERTAIN_M = 0.5

/** 0,30 m si l'emprise est MESURÉE ; 0,50 m dans tous les autres cas. */
export function degagementParProvenance(provenance) {
  return provenance === 'mesure' ? DEGAGEMENT_MESURE_M : DEGAGEMENT_INCERTAIN_M
}

/**
 * Dégagement EFFECTIF d'un obstacle.
 * → { valeur, derive, surcharge }
 * `surcharge` est vrai dès que la valeur saisie diffère de la valeur dérivée :
 * l'écran doit alors la badger « surchargé ».
 */
export function degagementEffectif(obstacle) {
  const derive = degagementParProvenance(obstacle?.provenance)
  const brut = obstacle?.degagementM
  if (brut === null || brut === undefined || brut === '') {
    return { valeur: derive, derive, surcharge: false }
  }
  const n = Number(String(brut).replace(',', '.'))
  if (!Number.isFinite(n) || n < 0) return { valeur: derive, derive, surcharge: false }
  return { valeur: n, derive, surcharge: Math.abs(n - derive) > 1e-9 }
}
