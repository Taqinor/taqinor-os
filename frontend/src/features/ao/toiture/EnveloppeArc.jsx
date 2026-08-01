/* AOF91 — Enveloppe en ARC : saisie PARAMÉTRIQUE, rendu développé ET rendu réel.
   ----------------------------------------------------------------------------
   Un arc ne se trace pas à la souris. On le SAISIT : rayon extérieur, largeur,
   longueurs développées des segments, épaisseur des murets qui les séparent.
   Le relevé de référence : R_ext 274,00 · largeur 10,90 (donc R_int 263,10) ·
   trois segments 20,55 + 23,00 + 23,60 séparés par deux murets de 0,45 —
   développé muret-à-muret 68,05 m.

   DEUX PIÈGES QUE CET ÉCRAN EXISTE POUR ÉVITER :

   1. UNE RANGÉE À CHEVAL SUR UN MURET. Chaque segment a son PROPRE plan de pose
      et ses rives d'extrémité (0,35 m) : une rangée proposée par-dessus un muret
      n'est pas une rangée « presque bonne », c'est une rangée impossible à
      poser. L'écran ne la propose donc jamais, et il l'affiche : « 0 rangée à
      cheval ».

   2. LE PAS DE POSE MESURÉ AU MAUVAIS RAYON. Poser les tables jointives en
      abscisse DÉVELOPPÉE (celle du bord extérieur) les fait se RECOUVRIR de
      quelques centimètres au rayon INTÉRIEUR — le bord intérieur est plus court.
      Le pas vaut donc `largeur_module × R_ext / (R_int + y0)`, évalué au bord
      intérieur (y0 = 0), là où la contrainte est la plus dure. L'écran affiche
      le recouvrement ainsi ÉVITÉ, en centimètres : c'est ce chiffre qui explique
      pourquoi on pose quelques modules de moins.

   Les deux rendus sont côte à côte parce qu'ils ne servent pas à la même chose :
   le développé est celui sur lequel on relève et on cote, le réel est celui que
   le maître d'ouvrage reconnaît sur sa toiture. */
import { useCallback, useMemo, useState } from 'react'

/* ── Géométrie pure (exportée : c'est elle que le test interroge) ───────────── */

export const ARC_REFERENCE = {
  rayonExtM: 274.0,
  largeurM: 10.9,
  riveM: 0.35,
  muretM: 0.45,
  segmentsM: [20.55, 23.0, 23.6],
}

function nombre(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(String(v).replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

function m(n) {
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

const CX = 0

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
  const marge = 1
  const x = Math.min(...xs) - marge
  const y = Math.min(...ys) - marge
  return {
    x,
    y,
    largeur: Math.max(...xs) - x + marge,
    hauteur: Math.max(...ys) - y + marge,
  }
}

/* ── Écran ──────────────────────────────────────────────────────────────────── */

export default function EnveloppeArc({
  valeurInitiale = ARC_REFERENCE,
  moduleLargeurM = 1.134,
  onValider,
}) {
  const [params, setParams] = useState(valeurInitiale)
  const [refus, setRefus] = useState(null)

  const majChamp = useCallback(
    (champ, valeur) => setParams((p) => ({ ...p, [champ]: valeur })),
    [],
  )

  const majSegments = useCallback((texte) => {
    setParams((p) => ({
      ...p,
      segmentsM: texte
        .split(/[;,\s]+/)
        .map((t) => t.trim())
        .filter(Boolean)
        .map((t) => Number(t.replace(',', '.'))),
    }))
  }, [])

  const controle = useMemo(() => validerArc(params), [params])
  const { arc, pas, rangees } = useMemo(
    () => rangeesProposees(params, moduleLargeurM),
    [params, moduleLargeurM],
  )
  const aCheval = useMemo(
    () => rangees.filter((r) => rangeeACheval(r, arc.murets)),
    [rangees, arc.murets],
  )
  const recouvrement = useMemo(
    () => recouvrementEvite(moduleLargeurM, arc.rayonExtM, arc.rayonIntM, 0),
    [moduleLargeurM, arc.rayonExtM, arc.rayonIntM],
  )

  // Centre de l'arc : à l'origine en X, au rayon extérieur en Y (l'arc « pend »
  // sous son centre), pour que le secteur tienne dans un viewBox positif.
  const boite = useMemo(
    () => (controle.valide ? boiteArc(arc, CX, arc.rayonExtM) : null),
    [controle.valide, arc],
  )

  const valider = useCallback(() => {
    const c = validerArc(params)
    if (!c.valide) {
      setRefus(c.motifs)
      return
    }
    setRefus(null)
    onValider?.({ ...params, ...decouperArc(params) })
  }, [params, onValider])

  const segmentsTexte = (params.segmentsM ?? []).join(' ')

  return (
    <section className="ao-enveloppe-arc" data-ao-enveloppe="arc">
      <h3>Enveloppe en arc</h3>

      <div className="ao-arc-parametres">
        <label className="ao-champ" htmlFor="ao-arc-rayon">
          <span>Rayon extérieur (m)</span>
          <input
            id="ao-arc-rayon"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.rayonExtM ?? ''}
            onChange={(e) => majChamp('rayonExtM', e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-arc-largeur">
          <span>Largeur de la bande (m)</span>
          <input
            id="ao-arc-largeur"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.largeurM ?? ''}
            onChange={(e) => majChamp('largeurM', e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-arc-segments">
          <span>Segments — longueurs développées (m)</span>
          <input
            id="ao-arc-segments"
            className="form-control"
            type="text"
            value={segmentsTexte}
            onChange={(e) => majSegments(e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-arc-muret">
          <span>Épaisseur des murets (m)</span>
          <input
            id="ao-arc-muret"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.muretM ?? ''}
            onChange={(e) => majChamp('muretM', e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-arc-rive">
          <span>Rive d’extrémité par segment (m)</span>
          <input
            id="ao-arc-rive"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.riveM ?? ''}
            onChange={(e) => majChamp('riveM', e.target.value)}
          />
        </label>
      </div>

      {refus && (
        <ul role="alert" data-ao-arc-refus={refus.length}>
          {refus.map((motif) => (
            <li key={motif}>{motif}</li>
          ))}
        </ul>
      )}

      <p data-ao-arc-developpe={arc.developpeTotal.toFixed(2)}>
        Développé muret-à-muret&nbsp;: {m(arc.developpeTotal)} m — rayon intérieur{' '}
        {m(arc.rayonIntM)} m sur {arc.segments.length} segment
        {arc.segments.length > 1 ? 's' : ''} et {arc.murets.length} muret
        {arc.murets.length > 1 ? 's' : ''}.
      </p>

      <p data-ao-arc-pas={pas.toFixed(4)}>
        Pas de pose corrigé&nbsp;: {pas.toFixed(3).replace('.', ',')} m pour une table de{' '}
        {m(moduleLargeurM)} m — {(recouvrement * 100).toFixed(1).replace('.', ',')} cm de
        recouvrement évité au rayon intérieur par table.
      </p>

      <p data-ao-arc-a-cheval={aCheval.length}>
        {rangees.length} rangée{rangees.length > 1 ? 's' : ''} proposée
        {rangees.length > 1 ? 's' : ''}, {aCheval.length} à cheval sur un muret.
      </p>

      {/* Les deux rendus, CÔTE À CÔTE : le développé sert au relevé, le réel est
          celui que le maître d'ouvrage reconnaît sur sa toiture. */}
      <div className="ao-arc-rendus">
        <figure className="ao-arc-rendu" data-ao-arc-rendu="developpe">
          <figcaption>Rendu développé</figcaption>
          <svg
            viewBox={`-1 -1 ${arc.developpeTotal + 2} ${arc.largeurM + 2}`}
            role="img"
            aria-label={`Développé de ${m(arc.developpeTotal)} mètres`}
            data-ao-canvas="arc-developpe"
          >
            {arc.segments.map((seg) => (
              <rect
                key={`s${seg.index}`}
                x={seg.debut}
                y={0}
                width={seg.longueur}
                height={arc.largeurM}
                className="ao-arc-segment"
                data-ao-arc-segment={seg.index}
              />
            ))}
            {arc.murets.map((mu) => (
              <rect
                key={`m${mu.index}`}
                x={mu.debut}
                y={0}
                width={mu.fin - mu.debut}
                height={arc.largeurM}
                className="ao-arc-muret"
                data-ao-arc-muret={mu.index}
              />
            ))}
            {rangees.map((r) => (
              <rect
                key={`r${r.debut.toFixed(3)}`}
                x={r.debut}
                y={0}
                width={r.fin - r.debut}
                height={arc.largeurM}
                className="ao-arc-rangee"
                fill="none"
              />
            ))}
          </svg>
        </figure>

        <figure className="ao-arc-rendu" data-ao-arc-rendu="reel">
          <figcaption>Rendu réel</figcaption>
          {boite ? (
            <svg
              viewBox={`${boite.x} ${boite.y} ${boite.largeur} ${boite.hauteur}`}
              role="img"
              aria-label={`Arc réel de rayon extérieur ${m(arc.rayonExtM)} mètres`}
              data-ao-canvas="arc-reel"
            >
              {arc.segments.map((seg) => (
                <path
                  key={`rs${seg.index}`}
                  d={cheminSecteur(arc, seg.debut, seg.fin, CX, arc.rayonExtM)}
                  className="ao-arc-segment"
                  data-ao-arc-segment-reel={seg.index}
                />
              ))}
              {arc.murets.map((mu) => (
                <path
                  key={`rm${mu.index}`}
                  d={cheminSecteur(arc, mu.debut, mu.fin, CX, arc.rayonExtM)}
                  className="ao-arc-muret"
                  data-ao-arc-muret-reel={mu.index}
                />
              ))}
            </svg>
          ) : (
            <p>Rendu réel indisponible tant que le rayon et la largeur ne sont pas saisis.</p>
          )}
        </figure>
      </div>

      <button type="button" onClick={valider} data-ao-arc-valider>
        Valider l’enveloppe en arc
      </button>
    </section>
  )
}
