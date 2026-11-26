import { useState } from 'react'
import { formatNumber } from '../../../lib/format'
import { useModeExpert } from '../atelier/modeExpert'
import { libelleSource } from './DiagrammePertes.helpers'
import useExplications from '../commun/useExplications'

/* ============================================================================
   ACAL880 — « POURQUOI CE CHIFFRE ? » SOUS LA PRODUCTION (niveau expert).
   ----------------------------------------------------------------------------
   Les trois étapes CALCULÉES de plus forte perte de la cascade servie
   (`resultat.cascade.etapes`, contrat `calepinage_pertes_cascade.json`) :
   libellé, perte et source TELLES QUE SERVIES, et le geste de leur entrée du
   registre (`pertes.<etape>`, sinon l'entrée commune `pertes.etape`). AUCUN
   calcul : un tri des pertes servies. Une étape omise (motif servi) ou de gain
   (bifacial : perte négative, ce n'est pas une perte) n'entre pas au classement.
   Aucune « plage habituelle » : sans plage publiée elle serait inventée.
   ========================================================================== */

const PREMIERES = 3 // la maquette `Resultats.dc.html` : trois postes

function postesDominants(cascade) {
  const etapes = Array.isArray(cascade?.etapes) ? cascade.etapes : []
  return etapes
    .filter((e) => typeof e?.perte_kwh === 'number' && e.gain !== true && !e.motif_omission)
    .sort((a, b) => b.perte_kwh - a.perte_kwh)
    .slice(0, PREMIERES)
}

export default function PourquoiProduction({ cascade }) {
  const [expert] = useModeExpert()
  const [ouvert, setOuvert] = useState(false)
  const entrees = useExplications()
  const postes = postesDominants(cascade)
  if (!expert || postes.length === 0) return null
  const geste = (etape) => (entrees?.find((e) => e.cle === `pertes.${etape}`)
    ?? entrees?.find((e) => e.cle === 'pertes.etape'))?.geste
  return (
    <div className="flex flex-col gap-2" data-testid="acal880-pourquoi">
      <button
        type="button"
        className="min-h-11 w-fit text-sm font-medium text-primary-text underline"
        aria-expanded={ouvert}
        onClick={() => setOuvert((v) => !v)}
        data-testid="acal880-bouton"
      >
        Pourquoi ce chiffre ?
      </button>
      {ouvert && (
        <ol className="flex flex-col gap-2 text-sm" data-testid="acal880-postes">
          {postes.map((p) => (
            <li key={p.etape} className="rounded-md border border-border p-3" data-testid={`acal880-poste-${p.etape}`}>
              <p className="font-medium">
                {p.libelle}{' — '}{formatNumber(p.perte_pct, { decimals: 1 })}{' %'}
                <span className="text-muted-foreground">{` (source : ${p.source ? libelleSource(p.source) : 'non publiée'})`}</span>
              </p>
              {geste(p.etape) && (
                <p className="text-muted-foreground" data-testid={`acal880-geste-${p.etape}`}>{geste(p.etape)}</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
