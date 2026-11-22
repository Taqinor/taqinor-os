/* ACAL1193 — les vignettes de l'écran Documents (maquette `Documents.dc.html`) : cinq petits plans
   à plat de 112 × 80, dessinés en SVG intégré, au trait de la maquette (toit vu de dessus, panneaux
   sombres en deux rangées, cotes ; schéma relié ; page de texte et tableau ; page avec histogramme ;
   contour DXF en traits fins). Aucune image : tout est jeton (`var(--…)`), le fond et le filet de la
   vignette viennent de la CSS. Ce sont des pictogrammes du TYPE de document, jamais le dessin du projet. */

const CADRE = { width: 112, height: 80, viewBox: '0 0 112 80', 'aria-hidden': 'true', focusable: 'false' }
const NAVY = 'var(--foreground)'
const OR = 'var(--primary)'
const FILET = 'var(--border)'
const SOURD = 'var(--muted-foreground)'
const PAGE = 'var(--card)'
const BLEU = 'var(--info)'

/** Une rangée de panneaux de 12 × 10 (pas 12), de `x0` à `x0 + 6 × 12`. */
function Rangee({ x0 = 19, y, plein = true }) {
  return [0, 1, 2, 3, 4, 5].map((i) => (
    <rect key={i} x={x0 + i * 12} y={y} width="12" height="10"
      fill={plein ? NAVY : 'none'} fillOpacity={plein ? 0.9 : undefined} stroke={plein ? PAGE : NAVY}
      strokeWidth=".8" />
  ))
}

function PlanDePose() {
  return (
    <svg {...CADRE}>
      <rect x="14" y="12" width="84" height="56" fill={PAGE} stroke={OR} strokeWidth="1.5" />
      <path d="M14 40h84" stroke={OR} strokeOpacity=".6" strokeWidth="1" />
      <Rangee y={43} />
      <Rangee y={53} />
      <path d="M14 6h84M14 4v4M98 4v4M104 12v56M102 12h4M102 68h4" stroke={SOURD} strokeWidth="1" fill="none" />
    </svg>
  )
}

function SchemaElectrique() {
  const boite = { fill: PAGE, stroke: NAVY, strokeWidth: 1.2 }
  return (
    <svg {...CADRE}>
      <g fill={BLEU}>
        <rect x="8" y="18" width="6" height="8" /><rect x="15" y="18" width="6" height="8" />
        <rect x="22" y="18" width="6" height="8" />
      </g>
      <g fill={SOURD}>
        <rect x="8" y="32" width="6" height="8" /><rect x="15" y="32" width="6" height="8" />
        <rect x="22" y="32" width="6" height="8" />
      </g>
      <path d="M28 22h12M28 36h12M58 29h12M86 29v20M86 58v6H66M50 64H40" fill="none" stroke={NAVY} strokeWidth="1.2" />
      <rect x="40" y="16" width="18" height="26" rx="2" {...boite} />
      <rect x="70" y="16" width="22" height="28" rx="2" {...boite} />
      <path d="M72 42l18-24" stroke={NAVY} strokeWidth="1" />
      <rect x="50" y="54" width="16" height="18" rx="2" {...boite} />
      <circle cx="32" cy="64" r="8" {...boite} />
    </svg>
  )
}

function NoteDeCalcul() {
  return (
    <svg {...CADRE}>
      <rect x="30" y="6" width="52" height="68" rx="2" fill={PAGE} stroke={FILET} />
      <path d="M36 14h30M36 20h40M36 25h36" stroke={NAVY} strokeWidth="1.6" />
      <rect x="36" y="32" width="40" height="26" fill="none" stroke={FILET} />
      <path d="M36 40h40M36 49h40M54 32v26" stroke={FILET} />
      <path d="M36 64h28M36 69h20" stroke={SOURD} strokeWidth="1.4" />
    </svg>
  )
}

function RapportDEtude() {
  const barres = [[37, 42, 10], [43, 38, 14], [49, 33, 19], [55, 30, 22], [61, 34, 18], [67, 40, 12]]
  return (
    <svg {...CADRE}>
      <rect x="30" y="6" width="52" height="68" rx="2" fill={PAGE} stroke={FILET} />
      <rect x="36" y="12" width="40" height="8" rx="1" fill={NAVY} />
      <g fill={OR}>
        {barres.map(([x, y, h]) => <rect key={x} x={x} y={y} width="4" height={h} />)}
      </g>
      <path d="M36 52h40" stroke={FILET} />
      <path d="M36 60h34M36 66h24" stroke={SOURD} strokeWidth="1.4" />
    </svg>
  )
}

function PlanDxf() {
  return (
    <svg {...CADRE}>
      <rect x="14" y="12" width="84" height="56" fill="none" stroke={BLEU} strokeWidth="1.2" />
      <path d="M14 40h84" stroke={BLEU} strokeWidth=".8" strokeDasharray="3 2" />
      <g fill="none" stroke={NAVY} strokeWidth=".8">
        <Rangee y={43} plein={false} />
        <Rangee y={53} plein={false} />
      </g>
      <rect x="74" y="18" width="8" height="8" fill="none" stroke={SOURD} strokeWidth="1" />
    </svg>
  )
}

const VIGNETTES = {
  plan_pose: PlanDePose,
  schema: SchemaElectrique,
  note_calcul: NoteDeCalcul,
  rapport_etude: RapportDEtude,
  dxf: PlanDxf,
}

export default function Vignette({ nom }) {
  const Dessin = VIGNETTES[nom]
  return Dessin ? <span className="cdoc-vignette" data-vignette={nom}><Dessin /></span> : null
}
