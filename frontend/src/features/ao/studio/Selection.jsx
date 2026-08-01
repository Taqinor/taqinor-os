import { useRef, useState } from 'react'
import {
  accrocher,
  appliquerSiValide,
  basculerSelection,
  deplacerPoints,
  indicesDansRectangle,
  pivoterPoints,
  rectangleDe,
  redimensionnerPoints,
  toleranceMetres,
} from './snap'
import { bboxDePoints } from './useViewport'

/* ============================================================================
   AOF76 — Sélection, poignées, accrochage : la VOIE SOURIS de l'éditeur.
   ----------------------------------------------------------------------------
   Se rend À L'INTÉRIEUR du groupe monde de `CanvasSvg` (mètres, y↑) : aucune
   conversion à la charge de l'appelant, et aucun `<text>` (il sortirait en
   miroir dans le groupe `scale(1,-1)` — les libellés de sommets vivent dans le
   tableau de géométrie d'AOF77).

   Toute la logique — accrochage, transformations, garde d'auto-intersection,
   règles de sélection — vit dans `snap.js` (pur, testé au node). Ce fichier ne
   fait que RENDRE et brancher des pointer events : c'est délibéré, un composant
   SVG n'est pas testable au node.

   Deux invariants tenus ici :
   · toute écriture passe par `appliquerSiValide` → une manipulation qui
     produirait un nœud papillon est REFUSÉE, la géométrie précédente est
     conservée et le motif est remonté (`onRefus`) ;
   · chaque poignée est un nœud focusable avec un anneau de focus VISIBLE
     (rendu explicitement : `box-shadow` ne s'applique pas aux nœuds SVG).
   ========================================================================== */

const R_POIGNEE_PX = 5
const R_ANGLE_PX = 6
const BRAS_ROTATION_PX = 28
const PAS_CLAVIER_M = 0.1

const lettreDe = (i) => String.fromCharCode(65 + (i % 26)) + (i >= 26 ? String(Math.floor(i / 26)) : '')

export function Selection({
  points = [],
  selection = [],
  onSelectionChange,
  survol = null,
  onSurvol,
  versMonde,
  metresParPixel = 0.05,
  zone = null,
  actif = true,
  accrochage = {},
  onGeometrie,
  onTerminer,
  onRefus,
  onGuides,
}) {
  const [focus, setFocus] = useState(null)
  const [marquee, setMarquee] = useState(null)
  const geste = useRef(null)

  const m = (px) => px * metresParPixel
  const boite = bboxDePoints(points)
  const centre = boite
    ? { x: (boite.xMin + boite.xMax) / 2, y: (boite.yMin + boite.yMax) / 2 }
    : null

  const ecrire = (suivants, libelle, cle) => {
    const r = appliquerSiValide(points, suivants)
    if (!r.valide) {
      onRefus?.(r.message)
      return
    }
    onGeometrie?.(r.points, libelle, { fusion: cle })
  }

  const finGeste = () => {
    geste.current = null
    onGuides?.([])
    onTerminer?.()
  }

  // ── Accrochage commun à tous les gestes ──────────────────────────────────
  const accrocherPoint = (pt, indexIgnore) => {
    const tolerance = toleranceMetres(metresParPixel, accrochage.tolerancePx)
    const sommets = points.filter((p, i) => i !== indexIgnore)
    const r = accrocher(pt, {
      actif: accrochage.actif !== false,
      sommets,
      references: [...sommets, ...(accrochage.references ?? [])],
      ancre: indexIgnore != null ? points[(indexIgnore - 1 + points.length) % points.length] : null,
      tolerance,
      pasAngle: accrochage.pasAngle,
    })
    onGuides?.(r.guides)
    return r
  }

  // ── Poignée de SOMMET : déplacement ──────────────────────────────────────
  const sommetDown = (index) => (e) => {
    e.stopPropagation()
    if (e.button != null && e.button !== 0) return
    onSelectionChange?.(basculerSelection(selection, index, e.shiftKey))
    if (e.shiftKey) return
    geste.current = {
      type: 'sommet', index, depart: points, cle: `sommet-${index}-${Date.now()}`,
    }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  const sommetMove = (e) => {
    const g = geste.current
    if (!g || g.type !== 'sommet' || !versMonde) return
    e.stopPropagation()
    const brut = versMonde(e)
    const { point, accroche } = accrocherPoint(brut, g.index)
    const suivants = points.map((p, i) => (i === g.index ? { ...p, x: point.x, y: point.y } : p))
    ecrire(
      suivants,
      accroche ? `Accrocher le sommet ${lettreDe(g.index)} (${accroche})` : `Déplacer le sommet ${lettreDe(g.index)}`,
      g.cle,
    )
  }

  // ── Poignée de REDIMENSIONNEMENT (coin) ──────────────────────────────────
  const coinDown = (coin) => (e) => {
    e.stopPropagation()
    if (!boite) return
    geste.current = {
      type: 'coin', coin, boite, depart: points, cle: `coin-${coin}-${Date.now()}`,
    }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  const coinMove = (e) => {
    const g = geste.current
    if (!g || g.type !== 'coin' || !versMonde) return
    e.stopPropagation()
    const pt = versMonde(e)
    const b = { ...g.boite }
    if (g.coin.includes('g')) b.xMin = Math.min(pt.x, b.xMax - 0.05)
    else b.xMax = Math.max(pt.x, b.xMin + 0.05)
    if (g.coin.includes('b')) b.yMin = Math.min(pt.y, b.yMax - 0.05)
    else b.yMax = Math.max(pt.y, b.yMin + 0.05)
    ecrire(redimensionnerPoints(g.depart, g.boite, b), 'Redimensionner le contour', g.cle)
  }

  // ── Poignée de ROTATION ──────────────────────────────────────────────────
  const rotationDown = (e) => {
    e.stopPropagation()
    if (!centre || !versMonde) return
    const pt = versMonde(e)
    geste.current = {
      type: 'rotation',
      centre,
      depart: points,
      angle0: Math.atan2(pt.y - centre.y, pt.x - centre.x),
      cle: `rotation-${Date.now()}`,
    }
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  const rotationMove = (e) => {
    const g = geste.current
    if (!g || g.type !== 'rotation' || !versMonde) return
    e.stopPropagation()
    const pt = versMonde(e)
    let angle = Math.atan2(pt.y - g.centre.y, pt.x - g.centre.x) - g.angle0
    if (e.shiftKey) {
      const pas = Math.PI / 12 // 15° au Maj — l'accrochage angulaire de la rotation
      angle = Math.round(angle / pas) * pas
    }
    const degres = Math.round((angle * 180) / Math.PI)
    ecrire(pivoterPoints(g.depart, g.centre, angle), `Pivoter de ${degres}°`, g.cle)
  }

  // ── Rectangle de sélection sur le fond ───────────────────────────────────
  const fondDown = (e) => {
    if (!versMonde || (e.button != null && e.button !== 0)) return
    const pt = versMonde(e)
    setMarquee({ depart: pt, courant: pt, additif: e.shiftKey })
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  const fondMove = (e) => {
    if (!marquee || !versMonde) return
    setMarquee((mq) => (mq ? { ...mq, courant: versMonde(e) } : mq))
  }

  const fondUp = () => {
    if (!marquee) return
    const rect = rectangleDe(marquee.depart, marquee.courant)
    const touches = indicesDansRectangle(points, rect)
    if (touches.length === 0 && !marquee.additif) onSelectionChange?.([])
    else if (marquee.additif) {
      onSelectionChange?.([...new Set([...selection, ...touches])].sort((a, b) => a - b))
    } else onSelectionChange?.(touches)
    setMarquee(null)
  }

  // ── Clavier : Échap annule le geste, les flèches déplacent la sélection ──
  const surTouche = (index) => (e) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      if (geste.current) {
        onGeometrie?.(geste.current.depart, 'Annuler le geste', {})
        finGeste()
      }
      setMarquee(null)
      onSelectionChange?.([])
      return
    }
    const pas = e.shiftKey ? PAS_CLAVIER_M * 10 : PAS_CLAVIER_M
    const deltas = {
      ArrowLeft: { dx: -pas, dy: 0 },
      ArrowRight: { dx: pas, dy: 0 },
      ArrowUp: { dx: 0, dy: pas },
      ArrowDown: { dx: 0, dy: -pas },
    }
    if (!deltas[e.key]) return
    e.preventDefault()
    e.stopPropagation()
    const cibles = selection.includes(index) ? selection : [index]
    ecrire(deplacerPoints(points, cibles, deltas[e.key]), `Déplacer le sommet ${lettreDe(index)}`)
    onTerminer?.()
  }

  const rMain = m(R_POIGNEE_PX)
  const rAngle = m(R_ANGLE_PX)
  const marqueeRect = marquee ? rectangleDe(marquee.depart, marquee.courant) : null

  return (
    <g
      onPointerMove={(e) => {
        sommetMove(e)
        coinMove(e)
        rotationMove(e)
        fondMove(e)
      }}
      onPointerUp={(e) => { fondUp(e); finGeste() }}
      onPointerCancel={() => { setMarquee(null); finGeste() }}
    >
      {/* Fond capteur du rectangle de sélection — actif seulement quand l'outil
          de sélection l'est, pour ne jamais voler le panoramique. */}
      {actif && zone && (
        <rect
          x={zone.xMin}
          y={zone.yMin}
          width={Math.max(zone.xMax - zone.xMin, 0)}
          height={Math.max(zone.yMax - zone.yMin, 0)}
          fill="transparent"
          onPointerDown={fondDown}
        />
      )}

      {marqueeRect && (
        <rect
          x={marqueeRect.xMin}
          y={marqueeRect.yMin}
          width={marqueeRect.xMax - marqueeRect.xMin}
          height={marqueeRect.yMax - marqueeRect.yMin}
          className="fill-primary/10 stroke-primary"
          strokeDasharray="4 3"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
          pointerEvents="none"
        />
      )}

      {/* Boîte de la sélection + poignées de coin et de rotation */}
      {boite && selection.length > 1 && (
        <>
          <rect
            x={boite.xMin}
            y={boite.yMin}
            width={boite.xMax - boite.xMin}
            height={boite.yMax - boite.yMin}
            fill="none"
            className="stroke-primary"
            strokeDasharray="5 4"
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
          {[
            ['bg', boite.xMin, boite.yMin], ['bd', boite.xMax, boite.yMin],
            ['hg', boite.xMin, boite.yMax], ['hd', boite.xMax, boite.yMax],
          ].map(([coin, cx, cy]) => (
            <rect
              key={coin}
              x={cx - rMain}
              y={cy - rMain}
              width={rMain * 2}
              height={rMain * 2}
              className="cursor-nwse-resize fill-card stroke-primary focus:outline-none"
              strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
              tabIndex={0}
              role="button"
              aria-label={`Redimensionner le contour (coin ${coin})`}
              onFocus={() => setFocus(`coin-${coin}`)}
              onBlur={() => setFocus(null)}
              onPointerDown={coinDown(coin)}
            />
          ))}
          {centre && (
            <>
              <line
                x1={centre.x}
                y1={boite.yMax}
                x2={centre.x}
                y2={boite.yMax + m(BRAS_ROTATION_PX)}
                className="stroke-primary"
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
              />
              <circle
                cx={centre.x}
                cy={boite.yMax + m(BRAS_ROTATION_PX)}
                r={rAngle}
                className="cursor-grab fill-card stroke-primary focus:outline-none"
                strokeWidth={1.5}
                vectorEffect="non-scaling-stroke"
                tabIndex={0}
                role="button"
                aria-label="Pivoter le contour"
                onFocus={() => setFocus('rotation')}
                onBlur={() => setFocus(null)}
                onPointerDown={rotationDown}
              />
              {focus === 'rotation' && (
                <circle
                  cx={centre.x}
                  cy={boite.yMax + m(BRAS_ROTATION_PX)}
                  r={rAngle * 2}
                  fill="none"
                  className="stroke-ring"
                  strokeWidth={2}
                  vectorEffect="non-scaling-stroke"
                  pointerEvents="none"
                />
              )}
            </>
          )}
        </>
      )}

      {/* Poignées de sommet — un nœud DOM par sommet : survol, sélection et
          focus clavier viennent gratuitement (c'est LA raison du SVG). */}
      {points.map((p, i) => {
        const choisi = selection.includes(i)
        const survole = survol === i
        return (
          <g key={`s-${i}`}>
            {(focus === `sommet-${i}` || survole) && (
              <circle
                cx={p.x}
                cy={p.y}
                r={rMain * 2}
                fill="none"
                className={focus === `sommet-${i}` ? 'stroke-ring' : 'stroke-primary/40'}
                strokeWidth={2}
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
              />
            )}
            <circle
              cx={p.x}
              cy={p.y}
              r={rMain}
              className={`cursor-move focus:outline-none ${choisi ? 'fill-primary stroke-card' : 'fill-card stroke-primary'}`}
              strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
              tabIndex={0}
              role="button"
              aria-label={`Sommet ${lettreDe(i)} — x ${p.x.toFixed(2)} m, y ${p.y.toFixed(2)} m`}
              aria-pressed={choisi}
              onFocus={() => { setFocus(`sommet-${i}`); onSurvol?.(i) }}
              onBlur={() => { setFocus(null); onSurvol?.(null) }}
              onPointerEnter={() => onSurvol?.(i)}
              onPointerLeave={() => onSurvol?.(null)}
              onPointerDown={sommetDown(i)}
              onKeyDown={surTouche(i)}
            />
          </g>
        )
      })}
    </g>
  )
}

export default Selection
