import { Link, useParams } from 'react-router-dom'
import { formatNumber } from '../../../lib/format'
import { useModeExpert } from '../atelier/modeExpert'
import { lienManque } from './lienManque'
import { estIncomplet } from './BandeauProvenanceProduction.helpers'
import { kwh, nonCalculee, nonPublie } from './ResultatHeros.helpers'
import { libelleAnneeBasse, cibleDuMotifDuree } from './LigneSurLaDuree.helpers'

/* ACAL710 — LA PRODUCTION SUR LA DURÉE : année basse (P90), dernière année de
   la projection et garantie du fabricant, puis le tableau « Sur N ans » replié.
   Tout est SERVI (`production.projection`, `duree_de_vie`, `total.p90_kwh`) :
   aucun calcul de production ni de garantie, aucun verdict « garantie tenue ».
   N vient de la dernière ligne de la projection (jamais 25 en dur) ; la
   garantie ne se lit qu'aux années 10 et 25, là où le fabricant la publie. */

const GARANTIE_PAR_ANNEE = { 10: 'pct_a_10_ans', 25: 'pct_a_25_ans' }

const garantieDe = (annee, garantie) => {
  const pct = garantie?.[GARANTIE_PAR_ANNEE[annee]]
  return typeof pct === 'number' ? pct : null
}

export default function LigneSurLaDuree({ production, incertitude = null }) {
  const [expert] = useModeExpert()
  const { id } = useParams()
  if (!expert) return null
  const total = production?.total
  const duree = production?.duree_de_vie
  const projection = Array.isArray(production?.projection) ? production.projection : []
  const omis = Boolean(duree?.motif_omission) || projection.length < 2
  const derniere = projection[projection.length - 1]
  const cibleMotif = cibleDuMotifDuree(duree?.motif_omission)
  const garantieFinale = garantieDe(derniere?.annee, duree?.garantie)
  const basse = estIncomplet(total) ? nonPublie(total?.p90_kwh_motif) : kwh(total?.p90_kwh)
  return (
    <div data-testid="acal710-ligne" className="flex flex-col gap-2 text-sm">
      <p>
        <span data-testid="acal710-basse">
          {libelleAnneeBasse(incertitude)} : {basse}
        </span>
        {!omis && (
          <span data-testid="acal710-derniere">
            {' · '}Dans {derniere.annee} ans : {kwh(derniere.p50_kwh)}
            {garantieFinale !== null && ` (garantie fabricant : ${formatNumber(garantieFinale, { decimals: 0 })} %)`}
          </span>
        )}
      </p>
      {omis ? (
        <p data-testid="acal710-motif" className="text-muted-foreground">
          {duree?.motif_omission || 'Aucune projection sur la durée n\'a été servie.'}
          {cibleMotif && id && (
            <>{' '}<Link to={lienManque(id, cibleMotif.cible)} className="text-primary-text underline">{cibleMotif.libelle}</Link></>
          )}
        </p>
      ) : (
        <details data-testid="acal710-tableau">
          <summary className="cursor-pointer text-muted-foreground">Sur {derniere.annee} ans</summary>
          <table className="mt-2 w-full text-left">
            <thead><tr><th>Année</th><th>Production (P50)</th><th>Facteur</th><th>Garantie</th></tr></thead>
            <tbody>
              {projection.map((ligne) => {
                const pct = garantieDe(ligne.annee, duree?.garantie)
                return (
                  <tr key={ligne.annee} data-testid={`acal710-annee-${ligne.annee}`}>
                    <td>{ligne.annee}</td>
                    <td>{kwh(ligne.p50_kwh)}</td>
                    <td>{nonCalculee(ligne.facteur, (x) => formatNumber(x, { decimals: 4 }))}</td>
                    <td>{pct === null ? '' : `${formatNumber(pct, { decimals: 0 })} %`}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </details>
      )}
    </div>
  )
}
