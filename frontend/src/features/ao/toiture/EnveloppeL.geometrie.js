/* AOF91 — Géométrie pure de l'enveloppe en « L » (extraite de EnveloppeL.jsx
   pour que ce module ne conserve QUE le composant —
   react-refresh/only-export-components).
   Le L se saisit comme UNE surface continue, jamais deux rectangles : une
   rangée qui reste du côté de l'aile descend d'un seul tenant de la barre
   dans l'aile, et découper le L en deux rectangles indépendants est une
   perte SÈCHE, chiffrée ici par `perteDuDecoupage`. */

export const L_REFERENCE = {
  barreLongueurM: 51.1,
  barreProfondeurM: 25.62,
  aileLongueurM: 18.0,
  aileProfondeurM: 12.0,
  coin: 'NE',
}

export const COINS = [
  { cle: 'NE', libelle: 'Nord-est' },
  { cle: 'NO', libelle: 'Nord-ouest' },
  { cle: 'SE', libelle: 'Sud-est' },
  { cle: 'SO', libelle: 'Sud-ouest' },
]

export function nombre(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(String(v).replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

export function m(n) {
  return Number(n).toFixed(2).replace('.', ',')
}

export function validerL(params = {}) {
  const motifs = []
  const L = nombre(params.barreLongueurM)
  const P = nombre(params.barreProfondeurM)
  const La = nombre(params.aileLongueurM)
  const Pa = nombre(params.aileProfondeurM)
  if (!(L > 0) || !(P > 0)) motifs.push('Barre incomplète : longueur et profondeur sont requises.')
  if (!(La > 0) || !(Pa > 0)) motifs.push("Aile incomplète : longueur et profondeur de l'aile sont requises.")
  if (L > 0 && La > 0 && La >= L) {
    motifs.push(
      `Aile (${m(La)} m) aussi longue que la barre (${m(L)} m) : c’est un rectangle, pas un L.`,
    )
  }
  return { valide: motifs.length === 0, motifs }
}

/**
 * LE contour — six sommets, un seul tenant. `coin` place l'aile ; le repère est
 * normalisé de sorte que le coin bas-gauche du rectangle englobant soit (0, 0).
 */
export function contourL(params = {}) {
  const L = nombre(params.barreLongueurM) ?? 0
  const P = nombre(params.barreProfondeurM) ?? 0
  const La = Math.min(nombre(params.aileLongueurM) ?? 0, L)
  const Pa = nombre(params.aileProfondeurM) ?? 0
  const coin = String(params.coin ?? 'NE').toUpperCase()
  const H = P + Pa

  let pts =
    coin[1] === 'E'
      ? [
          { x: 0, y: 0 },
          { x: L, y: 0 },
          { x: L, y: H },
          { x: L - La, y: H },
          { x: L - La, y: P },
          { x: 0, y: P },
        ]
      : [
          { x: 0, y: 0 },
          { x: L, y: 0 },
          { x: L, y: P },
          { x: La, y: P },
          { x: La, y: H },
          { x: 0, y: H },
        ]

  if (coin[0] === 'S') {
    // L'aile passe au sud : on retourne le repère et on rétablit le sens.
    pts = pts.map((p) => ({ x: p.x, y: H - p.y })).reverse()
  }
  return pts
}

/** Emprise E-O de l'aile, dans le repère du contour. */
export function empriseAile(params = {}) {
  const L = nombre(params.barreLongueurM) ?? 0
  const La = Math.min(nombre(params.aileLongueurM) ?? 0, L)
  return String(params.coin ?? 'NE').toUpperCase()[1] === 'E'
    ? { debut: L - La, fin: L }
    : { debut: 0, fin: La }
}

/**
 * Étendue N-S utile à l'abscisse `x` — la généralisation de `band()` au contour
 * concave. C'est elle qui prouve la continuité : sous l'aile, la bande va d'un
 * bord à l'autre SANS coupure.
 */
export function bandeL(params = {}, x) {
  const P = nombre(params.barreProfondeurM) ?? 0
  const Pa = nombre(params.aileProfondeurM) ?? 0
  const sud = String(params.coin ?? 'NE').toUpperCase()[0] === 'S'
  const aile = empriseAile(params)
  const sousAile = x >= aile.debut - 1e-9 && x <= aile.fin + 1e-9
  if (sousAile) return { ymin: 0, ymax: P + Pa, sousAile: true }
  return sud ? { ymin: Pa, ymax: Pa + P, sousAile: false } : { ymin: 0, ymax: P, sousAile: false }
}

/** Modules tenant dans une bande, rives comprises. */
export function modulesParBande(longueur, moduleM, riveM = 0.35) {
  const utile = Number(longueur) - 2 * Number(riveM)
  if (!(utile > 0) || !(Number(moduleM) > 0)) return 0
  return Math.floor(utile / Number(moduleM) + 1e-9)
}

/**
 * LA PREUVE CHIFFRÉE. Sous l'aile, un contour unique donne une bande de
 * (P + Pa) ; deux rectangles indépendants donnent P et Pa séparément, chacun
 * reprenant ses rives et perdant son reste. La différence, multipliée par le
 * nombre de bandes concernées, est la perte sèche du découpage.
 */
export function perteDuDecoupage(params = {}, { moduleM = 4.7, riveM = 0.35, pasM = 1.134 } = {}) {
  const P = nombre(params.barreProfondeurM) ?? 0
  const Pa = nombre(params.aileProfondeurM) ?? 0
  const aile = empriseAile(params)
  const largeurAile = Math.max(0, aile.fin - aile.debut)
  const bandes = pasM > 0 ? Math.floor((largeurAile - 2 * riveM) / pasM + 1e-9) : 0
  const continu = modulesParBande(P + Pa, moduleM, riveM)
  const decoupe = modulesParBande(P, moduleM, riveM) + modulesParBande(Pa, moduleM, riveM)
  const bandesSousAile = Math.max(0, bandes)
  return {
    bandesSousAile,
    continu,
    decoupe,
    parBande: continu - decoupe,
    perte: bandesSousAile * (continu - decoupe),
  }
}
