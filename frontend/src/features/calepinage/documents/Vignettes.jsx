/* ACAL1193 / ACAL1726 — les vignettes de l'écran Documents (maquette v2 `Documents.dc.html`) : cinq feuilles
   PORTRAIT (52 × 70) dessinées en SVG intégré, au trait de la maquette (plan de pose : toit, deux rangées
   de panneaux ; schéma relié ; note de calcul : texte et tableau ; rapport : bandeau et histogramme ;
   plan DXF : fond quadrillé, contours fins). Aucune image : tout est jeton `var(--cal-*)` (le thème sombre
   suit), le fond et l'ombre de la feuille viennent de la CSS. Ce sont des pictogrammes du TYPE de document,
   jamais le dessin du projet ni un chiffre : la même feuille, agrandie, sert de « modèle de page » dans la
   colonne d'aperçu quand la première page réelle n'est pas servie. */

const CADRE = { viewBox: '0 0 52 70', 'aria-hidden': 'true', focusable: 'false' }
const NAVY = 'var(--cal-texte-1)'
const OR = 'var(--cal-or-trait)'
const FILET = 'var(--cal-filet-fort)'
const SOURD = 'var(--cal-texte-3)'
const PAGE = 'var(--cal-surface)'
const PAPIER = 'var(--cal-papier)'
const BLEU = 'var(--cal-lien)'
const OK = 'var(--cal-ok)'
const PROD = 'var(--cal-production)'

function Feuille({ fond = PAGE, children }) {
  return (
    <svg {...CADRE}>
      <rect width="52" height="70" rx="2" fill={fond} stroke={FILET} />
      {children}
    </svg>
  )
}

function PlanDePose() {
  return (
    <Feuille>
      <rect x="5" y="5" width="18" height="3" rx="1.5" fill={NAVY} />
      <rect x="7" y="16" width="38" height="30" fill={PAPIER} stroke={OR} strokeWidth=".8" />
      <path d="M7 31h38" stroke={OR} strokeWidth=".5" />
      <rect x="20" y="32" width="23" height="6" fill={BLEU} />
      <rect x="20" y="39" width="23" height="6" fill={SOURD} />
      <path d="M20 32v13M24 32v13M28 32v13M32 32v13M36 32v13M40 32v13" stroke={PAGE} strokeWidth=".5" />
      <rect x="5" y="56" width="42" height="9" rx="1.5" fill={PAPIER} />
    </Feuille>
  )
}

function SchemaElectrique() {
  return (
    <Feuille>
      <rect x="5" y="5" width="18" height="3" rx="1.5" fill={NAVY} />
      <g fill={BLEU}><rect x="5" y="17" width="4" height="6" /><rect x="10" y="17" width="4" height="6" /></g>
      <g fill={SOURD}><rect x="5" y="27" width="4" height="6" /><rect x="10" y="27" width="4" height="6" /></g>
      <path d="M14 20h7" stroke={BLEU} strokeWidth=".9" />
      <path d="M14 30h7" stroke={SOURD} strokeWidth=".9" />
      <g fill="none" stroke={NAVY} strokeWidth=".9">
        <rect x="21" y="15" width="9" height="20" rx="1.5" />
        <rect x="36" y="15" width="11" height="34" rx="1.5" />
        <rect x="18" y="39" width="9" height="10" rx="1.5" />
        <circle cx="9" cy="44" r="3.5" />
        <path d="M30 22h6M30 28h6M36 44h-9M18 44h-6" />
      </g>
      <path d="M37.5 47l8-30" stroke={NAVY} strokeWidth=".6" />
      <path d="M8 56h36" stroke={SOURD} strokeWidth=".8" strokeDasharray="2 1.5" />
    </Feuille>
  )
}

function NoteDeCalcul() {
  return (
    <Feuille>
      <rect x="5" y="5" width="18" height="3" rx="1.5" fill={NAVY} />
      <g fill={NAVY} fillOpacity=".32"><rect x="5" y="13" width="36" height="2" rx="1" /><rect x="5" y="17" width="40" height="2" rx="1" /><rect x="5" y="21" width="30" height="2" rx="1" /></g>
      <rect x="5" y="27" width="42" height="22" rx="1" fill={PAPIER} stroke={FILET} strokeWidth=".6" />
      <path d="M5 34h42M5 41h42M22 27v22" stroke={FILET} strokeWidth=".6" />
      <g fill={OK}><rect x="26" y="29.5" width="12" height="2.5" rx="1" /><rect x="26" y="36.5" width="16" height="2.5" rx="1" /><rect x="26" y="43.5" width="10" height="2.5" rx="1" /></g>
      <g fill={NAVY} fillOpacity=".22"><rect x="5" y="55" width="32" height="2" rx="1" /><rect x="5" y="59" width="22" height="2" rx="1" /></g>
    </Feuille>
  )
}

function RapportDEtude() {
  const barres = [[7, 38, 8], [12, 34, 12], [17, 30, 16], [22, 27, 19], [27, 26, 20], [32, 29, 17], [37, 33, 13], [42, 37, 9]]
  return (
    <Feuille>
      <rect x="0" y="0" width="52" height="18" rx="2" fill={NAVY} />
      <rect x="5" y="6" width="20" height="3" rx="1.5" fill={PAGE} />
      <rect x="5" y="11" width="12" height="2" rx="1" fill={PROD} />
      <g fill={PROD}>{barres.map(([x, y, h]) => <rect key={x} x={x} y={y} width="3.5" height={h} rx="1" />)}</g>
      <path d="M5 46.5h42" stroke={NAVY} strokeOpacity=".2" strokeWidth=".6" />
      <path d="M8 32l5 2 5-1 5 2 5 1 5-2 5 1 5-2" fill="none" stroke={BLEU} strokeWidth=".9" />
      <g fill={NAVY} fillOpacity=".22"><rect x="5" y="54" width="34" height="2" rx="1" /><rect x="5" y="58" width="26" height="2" rx="1" /><rect x="5" y="62" width="30" height="2" rx="1" /></g>
    </Feuille>
  )
}

function PlanDxf() {
  const rangee = (y) => [20, 24, 28, 32, 36, 40].map((x) => <rect key={`${x}-${y}`} x={x} y={y} width="4" height="7" />)
  return (
    <Feuille fond={PAPIER}>
      <path d="M0 10h52M0 20h52M0 30h52M0 40h52M0 50h52M0 60h52M10 0v70M20 0v70M30 0v70M40 0v70" stroke={BLEU} strokeOpacity=".1" strokeWidth=".6" />
      <rect x="7" y="16" width="38" height="34" fill="none" stroke={BLEU} strokeWidth=".9" />
      <path d="M7 33h38" stroke={BLEU} strokeWidth=".6" strokeDasharray="2 1.5" />
      <g fill="none" stroke={NAVY} strokeWidth=".6">{rangee(34)}{rangee(41)}</g>
      <rect x="36" y="20" width="5" height="5" fill="none" stroke={SOURD} strokeWidth=".7" />
    </Feuille>
  )
}

const VIGNETTES = {
  plan_pose: PlanDePose,
  schema: SchemaElectrique,
  note_calcul: NoteDeCalcul,
  rapport_etude: RapportDEtude,
  dxf: PlanDxf,
}

/** `grande` : la feuille de la colonne d'aperçu (même dessin, plus grand). */
export default function Vignette({ nom, grande = false }) {
  const Dessin = VIGNETTES[nom]
  return Dessin ? <span className={`cdoc-vignette${grande ? ' cdoc-vignette-grande' : ''}`} data-vignette={nom}><Dessin /></span> : null
}
