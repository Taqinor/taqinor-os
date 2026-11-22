/* ACAL1193 — les vignettes de l'écran Documents (maquette `Documents.dc.html`) : cinq pictogrammes
   statiques de 112 × 80, dessinés en SVG intégré. Aucune image, aucune couleur écrite : tout est
   `currentColor` (la couleur du fond de vignette vient de la CSS, par jeton) avec des opacités. */

const CADRE = { width: 112, height: 80, viewBox: '0 0 112 80', fill: 'none', 'aria-hidden': 'true', focusable: 'false' }
const TRAIT = { stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round' }

function Panneaux({ x0, y0, lignes, colonnes, l = 14, h = 9, pas = 3 }) {
  const cases = []
  for (let r = 0; r < lignes; r += 1) {
    for (let c = 0; c < colonnes; c += 1) {
      cases.push(<rect key={`${r}-${c}`} x={x0 + c * (l + pas)} y={y0 + r * (h + pas)} width={l} height={h} rx="1.5"
        fill="currentColor" fillOpacity={0.18 + ((r + c) % 3) * 0.12} {...TRAIT} strokeWidth={1} />)
    }
  }
  return cases
}

function PlanDePose() {
  return (
    <svg {...CADRE}>
      <path d="M10 66V24l46-14 46 14v42z" {...TRAIT} fillOpacity="0.06" fill="currentColor" />
      <Panneaux x0={22} y0={26} lignes={3} colonnes={4} />
      <path d="M22 62h68" {...TRAIT} strokeWidth={1.2} strokeDasharray="3 3" />
      <path d="M10 72h92M10 69v6M102 69v6" {...TRAIT} strokeWidth={1} />
    </svg>
  )
}

function SchemaElectrique() {
  return (
    <svg {...CADRE}>
      <rect x="8" y="14" width="26" height="18" rx="2" fill="currentColor" fillOpacity="0.2" {...TRAIT} />
      <rect x="8" y="46" width="26" height="18" rx="2" fill="currentColor" fillOpacity="0.2" {...TRAIT} />
      <path d="M34 23h16v32H34M50 39h12" {...TRAIT} />
      <rect x="62" y="27" width="22" height="24" rx="3" fill="currentColor" fillOpacity="0.12" {...TRAIT} />
      <path d="M68 39h10M73 34v10" {...TRAIT} strokeWidth={1.2} />
      <path d="M84 39h10" {...TRAIT} />
      <circle cx="102" cy="39" r="8" {...TRAIT} />
      <path d="M98 39h8" {...TRAIT} strokeWidth={1.2} />
    </svg>
  )
}

function NoteDeCalcul() {
  return (
    <svg {...CADRE}>
      <path d="M30 8h38l14 14v50H30z" fill="currentColor" fillOpacity="0.06" {...TRAIT} />
      <path d="M68 8v14h14" {...TRAIT} />
      <path d="M38 34h34M38 42h26M38 50h30" {...TRAIT} strokeWidth={1.2} />
      <path d="M42 66h8M46 62v8M58 66h8" {...TRAIT} />
    </svg>
  )
}

function RapportDEtude() {
  const barres = [26, 34, 44, 52, 56, 50, 40]
  return (
    <svg {...CADRE}>
      <rect x="14" y="8" width="84" height="64" rx="4" fill="currentColor" fillOpacity="0.06" {...TRAIT} />
      <path d="M24 60h64" {...TRAIT} strokeWidth={1.2} />
      {barres.map((b, i) => (
        <rect key={`b${i}`} x={26 + i * 9} y={60 - b * 0.7} width="6" height={b * 0.7} rx="1"
          fill="currentColor" fillOpacity="0.4" />
      ))}
      <path d="M24 18h26" {...TRAIT} strokeWidth={1.2} />
    </svg>
  )
}

function PlanDxf() {
  return (
    <svg {...CADRE}>
      <path d="M14 14v52h84" {...TRAIT} />
      <path d="M22 58l26-30 24 12 16-14" {...TRAIT} strokeWidth={1.2} />
      <rect x="40" y="40" width="22" height="14" fill="currentColor" fillOpacity="0.2" {...TRAIT} strokeWidth={1.2} />
      <circle cx="22" cy="58" r="2.5" fill="currentColor" />
      <circle cx="88" cy="26" r="2.5" fill="currentColor" />
      <text x="82" y="62" fontSize="10" fontWeight="600" fill="currentColor" fontFamily="inherit">DXF</text>
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
