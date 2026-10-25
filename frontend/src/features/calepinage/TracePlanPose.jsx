import { formatCote, milieu } from './plan2d'
import { formatNumber } from '../../lib/format'

/* ============================================================================
   ENF19 — LE TRACÉ SVG PARTAGÉ DES PLANS DE POSE (terrain, ombrière, vue 2D).
   ----------------------------------------------------------------------------
   Le contour, le polygone plein d'une table / travée / module projeté et les
   cotes posées au milieu de chaque côté étaient recopiés à l'identique dans
   `ModeTerrain.jsx`, `Ombriere.jsx` et `Vue2DPlan.jsx` : chaque copie dérivait
   seule. Chaque écran garde SES `data-testid` (passés en paramètre) : le DOM
   rendu est inchangé.
   ========================================================================== */

const enPoints = (sommets) => sommets.map((p) => p.join(',')).join(' ')

/** Le contour (emprise, terrain, toit) : trait plein, sans remplissage. */
export function ContourPlan({ sommets, testid }) {
  return (
    <polygon
      data-testid={testid}
      points={enPoints(sommets)}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    />
  )
}

/** Un module / une table / une travée : polygone plein translucide. */
export function PolygonePose({ sommets, testid }) {
  return (
    <polygon
      data-testid={testid}
      points={enPoints(sommets)}
      fill="currentColor"
      fillOpacity="0.25"
      stroke="currentColor"
      strokeWidth="0.75"
    />
  )
}

/** Les cotes de longueur, posées au milieu de chaque segment. */
export function CotesPlan({ cotes, testid }) {
  return cotes.map((c, i) => {
    const [mx, my] = milieu(c.from, c.to)
    return (
      <text key={i} data-testid={testid} x={mx} y={my} fontSize="12" textAnchor="middle" fill="currentColor">
        {formatCote(c.lengthM)}
      </text>
    )
  })
}

/** Une rangée : trait pointillé entre ses deux extrémités. */
function RangeePlan({ rangee, testid }) {
  return (
    <line
      data-testid={testid}
      x1={rangee.from[0]}
      y1={rangee.from[1]}
      x2={rangee.to[0]}
      y2={rangee.to[1]}
      stroke="currentColor"
      strokeWidth="0.75"
      strokeDasharray="6 5"
      strokeOpacity="0.55"
    />
  )
}

/** La cote du pas inter-rangées : un trait et sa longueur au milieu. */
function CotePas({ cotePas, ids }) {
  const [mx, my] = milieu(cotePas.from, cotePas.to)
  return (
    <>
      <line
        data-testid={ids.traitPas}
        x1={cotePas.from[0]}
        y1={cotePas.from[1]}
        x2={cotePas.to[0]}
        y2={cotePas.to[1]}
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <text data-testid={ids.cotePas} x={mx} y={my} fontSize="12" textAnchor="middle" fill="currentColor">
        {formatCote(cotePas.lengthM)}
      </text>
    </>
  )
}

/**
 * Le plan d'une surface de pose posée par le moteur (`planVue2D`) : contour,
 * rangées, tables, cotes — et, quand l'écran fournit les `data-testid`
 * `traitPas` / `cotePas`, la cote du pas inter-rangées — suivi de la ligne
 * d'emprise rendue par le service (`champ`). `nom` est le mot de l'écran pour
 * une table posée (« table », « travée »), `titre` l'intitulé lu par les
 * lecteurs d'écran ; `ids` porte les `data-testid` propres à l'écran : `svg`,
 * `contour`, `rangee`, `table`, `cote`, `emprise`.
 */
export default function TracePlanPose({ vue, champ, ids, nom, titre }) {
  return (
    <>
      <svg
        data-testid={ids.svg}
        viewBox={`0 0 ${vue.largeurPx} ${vue.hauteurPx}`}
        width="100%"
        role="img"
        aria-label={`${titre} — ${vue.tables.length} ${nom}(s) posée(s) par le moteur`}
        className="mt-2 text-brass-200"
      >
        <ContourPlan sommets={vue.contour} testid={ids.contour} />
        {vue.rangees.map((r) => (
          <RangeePlan key={r.y0} rangee={r} testid={ids.rangee} />
        ))}
        {vue.tables.map((q, i) => (
          <PolygonePose key={i} sommets={q} testid={ids.table} />
        ))}
        <CotesPlan cotes={vue.cotes} testid={ids.cote} />
        {ids.traitPas && vue.cotePas && <CotePas cotePas={vue.cotePas} ids={ids} />}
      </svg>

      <p className="mt-2 text-xs text-lune-faint" data-testid={ids.emprise}>
        {vue.tables.length} {nom}(s) dessinée(s) — emprise{' '}
        {formatNumber(champ.empriseTablesM2, { decimals: 1 })} m² ;{' '}
        {champ.modules ?? '—'} module(s) posé(s) par le moteur.
      </p>
    </>
  )
}
