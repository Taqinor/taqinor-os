import { formatNumber } from '../../../lib/format'
import useExpertParUrl from '../production/useExpertParUrl'

/* ============================================================================
   ACAL789 — « DÉTAILS DE LA BATTERIE », MODE EXPERT SEULEMENT.
   Cycles par an, capacité année par année, pointe avant/après effacement et
   dépassements restants, lus TELS QUE SERVIS sous `batterie.total` : aucune
   valeur n'est recalculée ici. Une valeur absente se lit « non calculé » suivie
   du motif servi (`motif_absence` ou `champ`), jamais 0.
   ========================================================================== */

const JOURS_PAR_AN = 365
const MOTIF_STRATEGIE = 'cette valeur ne se calcule qu’en stratégie « Effacement de pointe ».'

const nombre = (v) => v !== null && v !== undefined && Number.isFinite(Number(v))

function NonCalcule({ motif }) {
  return <>non calculé{motif ? ` : ${motif}` : ''}</>
}

function LigneCycles({ vieillissement }) {
  const cycles = vieillissement?.cycles_annuels
  return (
    <li data-testid="acal789-cycles">
      Cycles par an :{' '}
      {nombre(cycles)
        ? `${formatNumber(cycles)} (en moyenne ${formatNumber(cycles / JOURS_PAR_AN, { decimals: 2 })} par jour)`
        : <NonCalcule motif={vieillissement?.motif_absence || vieillissement?.champ} />}
    </li>
  )
}

function LigneCapacite({ vieillissement }) {
  const annees = vieillissement?.annees
  return (
    <li data-testid="acal789-capacite">
      Capacité de la batterie :{' '}
      {Array.isArray(annees) && annees.length
        ? annees.map((a) => `année ${a.annee} ${nombre(a.capacite_batterie_pct)
          ? `${formatNumber(a.capacite_batterie_pct, { decimals: 1 })} %` : '—'}`).join(', ')
        : <NonCalcule motif={vieillissement?.motif_absence || vieillissement?.champ} />}
    </li>
  )
}

export default function ModeExpertBatterie({ batterie }) {
  const expert = useExpertParUrl()
  const total = batterie?.total
  if (!expert || !total) return null
  const motif = batterie.motif_absence || MOTIF_STRATEGIE
  const pointe = nombre(total.pointe_avant_kw) && nombre(total.pointe_apres_kw)
  return (
    <details className="flex flex-col gap-2" data-testid="acal789-details">
      <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold">Détails de la batterie</summary>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        <LigneCycles vieillissement={total.vieillissement} />
        <LigneCapacite vieillissement={total.vieillissement} />
        <li data-testid="acal789-pointe">
          Pointe :{' '}
          {pointe
            ? `${formatNumber(total.pointe_avant_kw, { decimals: 1 })} kW avant, ${formatNumber(total.pointe_apres_kw, { decimals: 1 })} kW après`
            : <NonCalcule motif={motif} />}
        </li>
        <li data-testid="acal789-depassements">
          Dépassements restants :{' '}
          {nombre(total.nombre_depassements_residuels)
            ? `${formatNumber(total.nombre_depassements_residuels)} heures par an`
            : <NonCalcule motif={motif} />}
        </li>
      </ul>
    </details>
  )
}
