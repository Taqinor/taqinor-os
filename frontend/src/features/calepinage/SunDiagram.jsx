import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { sortedHorizonPoints, horizonHeightAtAzimuth } from '@rooflib/horizonEngine'
import { sunDirection as sunPosition } from '@rooflib/roofPro2'
import { COURBES_REPERE } from './SunDiagram.helpers'
import { CHART_TOKENS } from '../../ui/charts/chart-theme.js'

/** ACAL449 — bornes d'une cellule : à mi-chemin de ses voisines, demi-pas au bord. */
function bornes(v, i, min, max) {
  const pas = v.length > 1 ? Math.abs(v[Math.min(i + 1, v.length - 1)] - v[Math.max(i - 1, 0)]) / (i === 0 || i === v.length - 1 ? 1 : 2) : max - min
  const lo = i === 0 ? v[i] - pas / 2 : (v[i - 1] + v[i]) / 2
  const hi = i === v.length - 1 ? v[i] + pas / 2 : (v[i] + v[i + 1]) / 2
  return [Math.max(min, lo), Math.min(max, hi)]
}

/** Les cellules de la table servie (`shadeTable`), sans interpolation ; facteur hors
 *  [0, 1] ou non fini → cellule écartée ; table absente ou mal formée → []. */
function cellulesOmbrage(table) {
  const az = table?.azimutsDeg
  const ha = table?.hauteursDeg
  if (!Array.isArray(az) || !Array.isArray(ha) || !Array.isArray(table?.facteurs) || !az.length || !ha.length) return []
  const out = []
  ha.forEach((_, j) => az.forEach((_a, i) => {
    const facteur = table.facteurs[j]?.[i]
    if (typeof facteur !== 'number' || !Number.isFinite(facteur) || facteur < 0 || facteur > 1) return
    const [az0, az1] = bornes(az, i, 0, 360)
    const [h0, h1] = bornes(ha, j, 0, 90)
    out.push({ az0, az1, h0, h1, facteur })
  }))
  return out
}

/** La course du soleil d'un jour, points AU-DESSUS de l'horizon seulement, tous les
 *  `stepH` heures — échantillonnée avec `sunDirection` du moteur (jamais une copie). */
function sunPathForDay(latDeg, dayOfYear, stepH = 0.25) {
  const points = []
  for (let h = 0; h <= 24; h += stepH) {
    const p = sunPosition(latDeg, dayOfYear, h)
    if (p.elevationDeg > 0) points.push({ ...p, hour: h })
  }
  return points
}

/* ============================================================================
   CAL93/CAL96 — LE DIAGRAMME AZIMUT/HAUTEUR PARTAGÉ.
   ----------------------------------------------------------------------------
   Extrait de `HorizonPanel.jsx` (CAL93) pour que `CourseSoleil.jsx` (CAL96)
   affiche EXACTEMENT le même repère (mêmes axes, même échelle, même tracé des
   trois jours de référence) plutôt que de réinventer une seconde projection —
   deux diagrammes qui divergent seraient pires que pas de diagramme.

   Pur : reçoit tout ce dont il a besoin en props, ne fait AUCUN appel réseau,
   ne calcule aucune géométrie d'obstruction (l'appelant la lui donne déjà en
   azimut/hauteur — `frontend/src/features/calepinage/obstructionMath.js` pour
   CAL96).
   ========================================================================== */

const LARGEUR = 640
const HAUTEUR = 260
const MARGE_G = 40
const MARGE_B = 24
const POLICE = 12 // ACAL1444 — unités du viewBox = px rendus dès que la largeur est mesurée
const GRADUATIONS = [0, 30, 60, 90]

/** ACAL1444 — le repère à la taille RENDUE : un viewBox fixe de 640 réduit à ≈ 270 px
 *  rendait les libellés à 5-6 px et le diagramme à 109 px de haut. */
function repere(largeur, hauteur) {
  const hautUtile = hauteur - MARGE_B - 10
  const xDe = (azimuthDeg) => MARGE_G + (azimuthDeg / 360) * (largeur - MARGE_G - 10)
  const yDe = (elevationDeg) => hautUtile - (Math.max(0, Math.min(90, elevationDeg)) / 90) * hautUtile
  return { largeur, hauteur, xDe, yDe }
}

/** Largeur rendue du SVG (px), `null` tant qu'elle n'est pas mesurable (jsdom, avant montage). */
function useLargeurRendue(ref) {
  const [largeur, setLargeur] = useState(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return undefined
    const lire = () => { const w = el.getBoundingClientRect().width; setLargeur(w > 0 ? Math.round(w) : null) }
    lire()
    const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(lire)
    ro?.observe(el)
    return () => ro?.disconnect()
  }, [ref])
  return largeur
}

/**
 * Le diagramme SVG azimut(x)/hauteur(y) : la course du soleil des trois jours de
 * référence, l'horizon lointain SAISI en aire pleine par-dessus, et les obstructions
 * PROCHES (CAL94) marquées à leur azimut/hauteur angulaire réels. `latitudeDeg` absente
 * → aucune course tracée (jamais une latitude devinée). `horizonPoints` < 2 points
 * exploitables → aucun horizon dessiné. `obstructions` vide → aucun marqueur — jamais
 * une donnée météo ou géométrique inventée.
 *
 * CALX118 — `sunDay`/`sunHour` (le soleil de SCÈNE, contrat CALX88 `scene{sunDay,
 * sunHour}`) positionnent un repère DISTINCT des trois courbes de référence : le MÊME
 * `sunPosition` (`@rooflib/roofPro2 sunDirection`, jamais une seconde formule) est appelé avec CES deux
 * valeurs. Absentes → aucun repère (comportement historique, byte pour byte) ; sous
 * l'horizon (élévation ≤ 0) → aucun repère non plus, jamais un point inventé sous terre.
 */
export default function SunDiagram({ latitudeDeg, horizonPoints = [], obstructions = [], sunDay, sunHour, tableOmbrage, ariaLabel, testId }) {
  const svgRef = useRef(null)
  const rendue = useLargeurRendue(svgRef)
  const { largeur, hauteur, xDe, yDe } = useMemo(() => (rendue
    ? repere(rendue, Math.max(220, Math.round((rendue * HAUTEUR) / LARGEUR))) : repere(LARGEUR, HAUTEUR)), [rendue])
  const sorted = sortedHorizonPoints(horizonPoints)
  const horizonPath = useMemo(() => {
    if (sorted.length < 2) return null
    const pas = 2
    let d = `M ${xDe(0)} ${yDe(0)}`
    for (let az = 0; az <= 360; az += pas) {
      const h = horizonHeightAtAzimuth(sorted, az) ?? 0
      d += ` L ${xDe(az)} ${yDe(h)}`
    }
    d += ` L ${xDe(360)} ${yDe(0)} Z`
    return d
  }, [sorted, xDe, yDe])

  // CALX118 — le repère du soleil de SCÈNE (`scene.sunDay`/`scene.sunHour`), MÊME
  // formule que les trois courbes de référence ci-dessous (`sunPosition`). Sous
  // l'horizon (nuit à cette heure/ce jour) → aucun repère, jamais un point inventé.
  const soleilCourant = useMemo(() => {
    if (typeof latitudeDeg !== 'number' || typeof sunDay !== 'number' || typeof sunHour !== 'number') return null
    const pos = sunPosition(latitudeDeg, sunDay, sunHour)
    return pos.elevationDeg > 0 ? pos : null
  }, [latitudeDeg, sunDay, sunHour])

  // ACAL449 — la table d'ombrage SERVIE (ACAL459), cellule par cellule ; absente → rien.
  const cellules = useMemo(() => cellulesOmbrage(tableOmbrage), [tableOmbrage])

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${largeur} ${hauteur}`}
      role="img"
      aria-label={ariaLabel ?? 'Course du soleil, par azimut et hauteur'}
      className="w-full"
      data-testid={testId ?? 'cal-sundiagram'}
    >
      {[0, 90, 180, 270, 360].map((az, i) => (
        <text key={az} x={xDe(az)} y={hauteur - 6} fontSize={POLICE} fill="#8f9bb8" textAnchor="middle">
          {['N', 'E', 'S', 'O', 'N'][i]}
        </text>
      ))}
      {/* ACAL1444 — axe vertical gradué en degrés de hauteur du soleil. */}
      {GRADUATIONS.map((g) => (
        <g key={g} data-testid="cal-sundiagram-graduation">
          {g > 0 && <line x1={MARGE_G} y1={yDe(g)} x2={largeur - 10} y2={yDe(g)} stroke="#3a4258" strokeWidth="0.5" strokeDasharray="3 3" />}
          <text x={MARGE_G - 4} y={yDe(g) + 4} fontSize={POLICE} fill="#8f9bb8" textAnchor="end">{`${g}°`}</text>
        </g>
      ))}
      {/* ACAL449 — cellules teintées, sans interpolation : opacité = 1 − facteur, SOUS la course. */}
      {cellules.map((c) => (
        <rect
          key={`${c.az0}-${c.h0}`}
          data-testid="acal449-cellule"
          data-facteur={c.facteur}
          x={xDe(c.az0)}
          y={yDe(c.h1)}
          width={xDe(c.az1) - xDe(c.az0)}
          height={yDe(c.h0) - yDe(c.h1)}
          fill={CHART_TOKENS.danger}
          fillOpacity={1 - c.facteur}
        />
      ))}
      <line x1={MARGE_G} y1={yDe(0)} x2={largeur - 10} y2={yDe(0)} stroke="#3a4258" strokeWidth="1" />

      {typeof latitudeDeg === 'number' &&
        COURBES_REPERE.map((c) => {
          const path = sunPathForDay(latitudeDeg, c.jour, 0.5)
          if (!path.length) return null
          const d = path.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xDe(p.azimuthDeg)} ${yDe(p.elevationDeg)}`).join(' ')
          return <path key={c.jour} d={d} fill="none" stroke={c.couleur} strokeWidth="1.5" opacity="0.85" />
        })}

      {horizonPath && <path d={horizonPath} fill="rgba(90,60,30,0.55)" stroke="#a06a2a" strokeWidth="1.5" />}

      {/* CAL94 — obstructions PROCHES, marquées à leur azimut/hauteur angulaire réels. */}
      {obstructions.map((o, i) => (
        <g key={`${o.label ?? 'obs'}-${i}`} data-testid="cal-sundiagram-obstruction">
          <circle cx={xDe(o.azimuthDeg)} cy={yDe(o.elevationDeg)} r="4" fill="#d0654f" stroke="#070b1d" strokeWidth="1" />
          {o.label && (
            <text x={xDe(o.azimuthDeg)} y={yDe(o.elevationDeg) - 7} fontSize={POLICE} fill="#d0654f" textAnchor="middle">
              {o.label}
            </text>
          )}
        </g>
      ))}

      {/* CALX118 — le soleil de SCÈNE courant, distinct des trois courbes de repère : un
          disque plein (jamais confondu avec une obstruction, marquée en rouge). */}
      {soleilCourant && (
        <g data-testid="cal-sundiagram-soleil-courant">
          <circle
            cx={xDe(soleilCourant.azimuthDeg)}
            cy={yDe(soleilCourant.elevationDeg)}
            r="6"
            fill="#ffd166"
            stroke="#070b1d"
            strokeWidth="1.5"
          />
        </g>
      )}
    </svg>
  )
}
