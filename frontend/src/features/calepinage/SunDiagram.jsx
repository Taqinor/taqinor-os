/* eslint-disable react-refresh/only-export-components --
   `COURBES_REPERE` (jours de repère + couleurs) est partagé par `HorizonPanel.jsx` et
   `CourseSoleil.jsx` pour peindre la MÊME légende que ce composant trace — le séparer
   dans un troisième fichier serait une indirection sans bénéfice pour deux consommateurs
   du même repère. */
import { useMemo } from 'react'
import { sortedHorizonPoints, horizonHeightAtAzimuth, sunPathForDay, JOUR_EQUINOXE, JOUR_SOLSTICE_ETE, JOUR_SOLSTICE_HIVER } from './horizonMath'

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
const HAUT_UTILE = HAUTEUR - MARGE_B - 10

function xDe(azimuthDeg) {
  return MARGE_G + (azimuthDeg / 360) * (LARGEUR - MARGE_G - 10)
}
function yDe(elevationDeg) {
  const clamped = Math.max(0, Math.min(90, elevationDeg))
  return HAUT_UTILE - (clamped / 90) * HAUT_UTILE
}

export const COURBES_REPERE = [
  { jour: JOUR_SOLSTICE_ETE, label: 'Solstice d’été', couleur: '#e0b25c' },
  { jour: JOUR_EQUINOXE, label: 'Équinoxe', couleur: '#8f9bb8' },
  { jour: JOUR_SOLSTICE_HIVER, label: 'Solstice d’hiver', couleur: '#5c7ce0' },
]

/**
 * Le diagramme SVG azimut(x)/hauteur(y) : la course du soleil des trois jours de
 * référence, l'horizon lointain SAISI en aire pleine par-dessus, et les obstructions
 * PROCHES (CAL94) marquées à leur azimut/hauteur angulaire réels. `latitudeDeg` absente
 * → aucune course tracée (jamais une latitude devinée). `horizonPoints` < 2 points
 * exploitables → aucun horizon dessiné. `obstructions` vide → aucun marqueur — jamais
 * une donnée météo ou géométrique inventée.
 */
export default function SunDiagram({ latitudeDeg, horizonPoints = [], obstructions = [], ariaLabel, testId }) {
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
  }, [sorted])

  return (
    <svg
      viewBox={`0 0 ${LARGEUR} ${HAUTEUR}`}
      role="img"
      aria-label={ariaLabel ?? 'Course du soleil, par azimut et hauteur'}
      className="w-full"
      data-testid={testId ?? 'cal-sundiagram'}
    >
      {[0, 90, 180, 270, 360].map((az, i) => (
        <text key={az} x={xDe(az)} y={HAUTEUR - 6} fontSize="11" fill="#8f9bb8" textAnchor="middle">
          {['N', 'E', 'S', 'O', 'N'][i]}
        </text>
      ))}
      <line x1={MARGE_G} y1={yDe(0)} x2={LARGEUR - 10} y2={yDe(0)} stroke="#3a4258" strokeWidth="1" />

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
            <text x={xDe(o.azimuthDeg)} y={yDe(o.elevationDeg) - 7} fontSize="10" fill="#d0654f" textAnchor="middle">
              {o.label}
            </text>
          )}
        </g>
      ))}
    </svg>
  )
}
