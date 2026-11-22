import { formatNumber, formatPercent } from '../../../lib/format'
import { Stat } from '../../../ui'
import { useModeExpert } from '../atelier/modeExpert'
import TuileCouverture from './TuileCouverture'
import { estIncomplet } from './BandeauProvenanceProduction.helpers'
import Pourquoi from '../commun/Pourquoi'
import {
  kwh, kwhParKwc, nonCalculee, nonPublie, pourcentagePerf,
} from './ResultatHeros.helpers'

/* ACAL443 — LA HIÉRARCHIE DU RÉSULTAT : un chiffre héros (P50 annuel), trois
   secondaires, le détail statistique replié. Aucun calcul : chaque valeur est
   celle de `production.total` servie ; `null` s'écrit « non calculée », jamais 0.
   Sans simulation (jamais lancée ou périmée), AUCUNE tuile : un seul état. */

export default function ResultatHeros({ total, simule, motif, avertissements, plages = null, autoconsommation = null }) {
  const [expert] = useModeExpert()
  if (!simule) {
    return (
      <div data-testid="acal443-non-calcule" className="rounded-md border border-border/60 p-4">
        <p className="text-sm font-medium">Production non calculée</p>
        <p className="text-sm text-muted-foreground">
          {avertissements?.[0] || motif || 'Aucune valeur de production n\'a encore été calculée.'}
        </p>
      </div>
    )
  }
  const incomplet = estIncomplet(total)
  const publie = (v, m) => (incomplet ? nonPublie(m) : kwh(v))
  // ACAL873 — le « ? » de chaque tuile : phrase du registre, valeurs servies.
  // Clés LITTÉRALES : la garde du registre (explications.garde.test.js) les lit.
  const servi = { production: { total } }
  return (
    <div className="flex flex-col gap-3" data-testid="cal236-total">
      <Stat
        tone="impact"
        label={<>Production annuelle (P50)<Pourquoi cle="production.p50_kwh" valeurs={servi} /></>}
        value={kwh(total?.p50_kwh)}
        hint={incomplet && total?.mention ? total.mention : undefined}
        data-testid="acal443-heros"
      />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Stat label={<>Puissance installée<Pourquoi cle="production.kwc" valeurs={servi} /></>}
          value={nonCalculee(total?.kwc, (x) => `${formatNumber(x, { decimals: 2 })} kWc`)} />
        <Stat label={<>Productible<Pourquoi cle="production.productible" valeurs={servi} /></>}
          value={kwhParKwc(total?.specific_yield_kwh_kwc)} />
        <Stat label={<>Pertes totales<Pourquoi cle="production.pertes_totales" valeurs={servi} /></>}
          value={nonCalculee(total?.total_loss_pct,
          (x) => formatPercent(x, { decimals: 1 }))}
        hint={expert && plages?.total ? (
          <span data-testid="acal703-total-plage">
            {plages.total.statut === 'dans_la_plage'
              ? 'Dans la plage habituelle' : 'Hors de la plage habituelle'}
          </span>
        ) : undefined} />
      </div>
      {expert && <TuileCouverture autoconsommation={autoconsommation} />}
      <details data-testid="acal443-details">
        <summary className="cursor-pointer text-sm text-muted-foreground">
          Détails statistiques
        </summary>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Stat label={<>P75 (annuel)<Pourquoi cle="production.p75_kwh" valeurs={servi} /></>}
            value={publie(total?.p75_kwh, total?.p75_kwh_motif)} />
          <Stat label={<>P90 (annuel)<Pourquoi cle="production.p90_kwh" valeurs={servi} /></>}
            value={publie(total?.p90_kwh, total?.p90_kwh_motif)} />
          <Stat label={<>P95 (annuel)<Pourquoi cle="production.p95_kwh" valeurs={servi} /></>}
            value={publie(total?.p95_kwh, total?.p95_kwh_motif)} />
          <Stat
            label={<>Variabilité annuelle (σ)<Pourquoi cle="production.variabilite" /></>}
            value={nonCalculee(total?.annual_variability,
              (x) => formatPercent(x * 100, { decimals: 1 }))}
          />
          <Stat
            label={<>Ratio de performance (PR)<Pourquoi cle="production.performance_ratio" /></>}
            value={incomplet ? nonPublie(total?.performance_ratio_motif)
              : pourcentagePerf(total?.performance_ratio)}
          />
        </div>
      </details>
    </div>
  )
}
