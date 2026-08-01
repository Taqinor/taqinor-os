/* AOF91 — Géométrie pure de l'enveloppe en arc (extraite de EnveloppeArc.jsx pour
   que ce module ne conserve QUE le composant — react-refresh/only-export-components).
   Le relevé de référence : R_ext 274,00 · largeur 10,90 (donc R_int 263,10) ·
   trois segments 20,55 + 23,00 + 23,60 séparés par deux murets de 0,45 —
   développé muret-à-muret 68,05 m. */

export const ARC_REFERENCE = {
  rayonExtM: 274.0,
  largeurM: 10.9,
  riveM: 0.35,
  muretM: 0.45,
  segmentsM: [20.55, 23.0, 23.6],
}

export function nombre(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(String(v).replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

export function m(n) {
  return Number(n).toFixed(2).replace('.', ',')
}

/**
 * Refus EXPLICITE et motivé. Un arc sans rayon ni largeur n'est pas « un arc
 * incomplet » : c'est une saisie qui ne décrit aucune surface, et le laisser
 * passer produirait un calepinage silencieusement faux.
 */
export function validerArc(params = {}) {
  const motifs = []
  const rayonExtM = nombre(params.rayonExtM)
  const largeurM = nombre(params.largeurM)
  const segments = (params.segmentsM ?? []).map(nombre).filter((v) => v !== null && v > 0)

  if (rayonExtM === null || rayonExtM <= 0) {
    motifs.push('Rayon extérieur manquant : sans rayon, un arc n’a ni développé ni courbure.')
  }
  if (largeurM === null || largeurM <= 0) {
    motifs.push('Largeur de la bande manquante : sans largeur, la surface posable est nulle.')
  }
  if (rayonExtM !== null && largeurM !== null && largeurM >= rayonExtM) {
    motifs.push(
      `Largeur (${m(largeurM)} m) supérieure ou égale au rayon extérieur (${m(
        rayonExtM,
      )} m) : le rayon intérieur serait négatif.`,
    )
  }
  if (segments.length === 0) {
    motifs.push('Aucun segment : indiquez au moins une longueur développée.')
  }
  return { valide: motifs.length === 0, motifs }
}

/**
 * Découpe l'arc en segments séparés par les murets, en abscisse DÉVELOPPÉE
 * (mesurée sur le bord extérieur, comme le relevé muret-à-muret).
 */
export function decouperArc(params = {}) {
  const rayonExtM = nombre(params.rayonExtM) ?? 0
  const largeurM = nombre(params.largeurM) ?? 0
  const riveM = nombre(params.riveM) ?? 0
  const muretM = nombre(params.muretM) ?? 0
  const longueurs = (params.segmentsM ?? []).map(nombre).filter((v) => v !== null && v > 0)

  const rayonIntM = rayonExtM - largeurM
  const segments = []
  const murets = []
  let curseur = 0
  longueurs.forEach((longueur, index) => {
    if (index > 0 && muretM > 0) {
      murets.push({ index: index - 1, debut: curseur, fin: curseur + muretM })
      curseur += muretM
    }
    const debut = curseur
    const fin = curseur + longueur
    segments.push({
      index,
      debut,
      fin,
      longueur,
      // Rives d'extrémité : chaque segment se pose entre ses propres rives.
      utileDebut: debut + riveM,
      utileFin: fin - riveM,
      utile: Math.max(0, longueur - 2 * riveM),
    })
    curseur = fin
  })

  return {
    rayonExtM,
    rayonIntM,
    largeurM,
    riveM,
    muretM,
    segments,
    murets,
    developpeTotal: curseur,
    angleTotalRad: rayonExtM > 0 ? curseur / rayonExtM : 0,
  }
}

/**
 * Pas de pose en abscisse développée pour une table de largeur `moduleM`,
 * évalué à l'ordonnée `y0` comptée DEPUIS LE BORD INTÉRIEUR.
 * `y0 = 0` (défaut) = le bord le plus court = la contrainte la plus dure.
 */
export function pasDePose(moduleM, rayonExtM, rayonIntM, y0 = 0) {
  const denom = Number(rayonIntM) + Number(y0)
  if (!(denom > 0) || !(Number(rayonExtM) > 0)) return Number(moduleM)
  return (Number(moduleM) * Number(rayonExtM)) / denom
}

/** Recouvrement (en m) qu'aurait provoqué un pas naïf, par table. */
export function recouvrementEvite(moduleM, rayonExtM, rayonIntM, y0 = 0) {
  return pasDePose(moduleM, rayonExtM, rayonIntM, y0) - Number(moduleM)
}

/**
 * Rangées proposées, segment par segment. Une rangée n'existe QUE si elle tient
 * entièrement entre les rives de SON segment : rien n'est jamais proposé à
 * cheval sur un muret.
 */
export function rangeesProposees(params = {}, moduleM = 1.134) {
  const arc = decouperArc(params)
  const pas = pasDePose(moduleM, arc.rayonExtM, arc.rayonIntM, 0)
  const rangees = []
  if (!(pas > 0)) return { arc, pas, rangees }
  for (const seg of arc.segments) {
    let x = seg.utileDebut
    while (x + pas <= seg.utileFin + 1e-9) {
      rangees.push({ segment: seg.index, debut: x, fin: x + pas })
      x += pas
    }
  }
  return { arc, pas, rangees }
}

/** Une rangée chevauche-t-elle l'un des murets ? (doit TOUJOURS être faux) */
export function rangeeACheval(rangee, murets = []) {
  return murets.some((mu) => rangee.debut < mu.fin - 1e-9 && rangee.fin > mu.debut + 1e-9)
}

/* ── Rendu : développé et réel ──────────────────────────────────────────────── */

function pointArc(cx, cy, rayon, angle) {
  return [cx + rayon * Math.sin(angle), cy - rayon * Math.cos(angle)]
}

/** Chemin SVG d'un secteur d'anneau entre deux abscisses développées. */
export function cheminSecteur(arc, debut, fin, cx, cy) {
  const { rayonExtM: re, rayonIntM: ri, angleTotalRad: total } = arc
  if (!(re > 0) || !(ri > 0)) return ''
  const a0 = debut / re - total / 2
  const a1 = fin / re - total / 2
  const [x0e, y0e] = pointArc(cx, cy, re, a0)
  const [x1e, y1e] = pointArc(cx, cy, re, a1)
  const [x1i, y1i] = pointArc(cx, cy, ri, a1)
  const [x0i, y0i] = pointArc(cx, cy, ri, a0)
  const grand = a1 - a0 > Math.PI ? 1 : 0
  return [
    `M ${x0e.toFixed(3)} ${y0e.toFixed(3)}`,
    `A ${re} ${re} 0 ${grand} 1 ${x1e.toFixed(3)} ${y1e.toFixed(3)}`,
    `L ${x1i.toFixed(3)} ${y1i.toFixed(3)}`,
    `A ${ri} ${ri} 0 ${grand} 0 ${x0i.toFixed(3)} ${y0i.toFixed(3)}`,
    'Z',
  ].join(' ')
}

/** Boîte englobante du secteur complet, pour un viewBox qui cadre tout seul. */
export function boiteArc(arc, cx, cy) {
  const { rayonExtM: re, rayonIntM: ri, angleTotalRad: total } = arc
  const pts = []
  const pas = Math.max(total / 24, 1e-3)
  for (let a = -total / 2; a <= total / 2 + 1e-9; a += pas) {
    pts.push(pointArc(cx, cy, re, a), pointArc(cx, cy, ri, a))
  }
  pts.push(pointArc(cx, cy, re, total / 2), pointArc(cx, cy, ri, total / 2))
  const xs = pts.map((p) => p[0])
  const ys = pts.map((p) => p[1])
  // `bordure` : respiration du viewBox, en mètres de dessin. Ce n'est PAS une
  // marge métier (marge de tronçon / de bande, cf. AOF101) — la nommer
  // autrement évite de laisser croire qu'un chiffre du moteur se calcule ici.
  const bordure = 1
  const x = Math.min(...xs) - bordure
  const y = Math.min(...ys) - bordure
  return {
    x,
    y,
    largeur: Math.max(...xs) - x + bordure,
    hauteur: Math.max(...ys) - y + bordure,
  }
}
