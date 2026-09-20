import { useParams } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber, formatPercent } from '../../../lib/format'
import { Card, Spinner, Stat } from '../../../ui'

/* ============================================================================
   CAL236 — LE PANNEAU « PRODUCTION » DU MODULE.
   ----------------------------------------------------------------------------
   Constat (PACT11) : toute la chaîne de simulation est déjà backend (CAL138
   par pan, CAL139 pertes, CAL142 P50/P90) mais aucun écran ne montre le
   RÉSULTAT — ce panneau comble ce trou, alimenté PAR le contrat partagé
   `apps/calepinage/contract_samples/calepinage_resultat.json` (CAL244,
   `resultat_calepinage`) via `calepinageApi.calepinages.resultat(id)`.

   AUCUN CALCUL CÔTÉ ÉCRAN. Chaque grandeur affichée est EXACTEMENT celle que
   le serveur renvoie sous `production` ; ce panneau ne fait que la mettre en
   forme (`formatNumber`/`formatPercent`, jamais `toLocaleString`).

   LA DISCIPLINE DU NULL (même que `VariantesCompare.jsx`, CAL42) : le contrat
   distingue un calepinage POSÉ-mais-NON-SIMULÉ (`simule: false`, toutes les
   grandeurs de `production` valent `null`) d'un calepinage simulé. `null`
   s'affiche « non calculée », JAMAIS `0` — un `0 kWh` se lirait « cette
   toiture ne produit rien » là où personne n'a lancé de simulation. Un pan
   SANS module affiche en revanche un vrai `0` (`modules: 0`, une mesure), pas
   « non calculée » : `formatNumber` ne confond jamais les deux, il ne rend
   « — » QUE sur `null`/`undefined`.
   ========================================================================== */

/** Une grandeur absente du serveur s'écrit « non calculée », jamais « — » nu
    ni `0` : c'est le vocabulaire que CAL236 impose (Done, PLAN2.md). */
function nonCalculee(valeur, rendu) {
  return valeur === null || valeur === undefined ? 'non calculée' : rendu(valeur)
}

const kwh = (v) => nonCalculee(v, (x) => `${formatNumber(x, { decimals: 0 })} kWh`)
const pourcentagePerf = (v) => nonCalculee(v, (x) => formatPercent(x * 100, { decimals: 1 }))
const kwhParKwc = (v) => nonCalculee(v, (x) => `${formatNumber(x, { decimals: 1 })} kWh/kWc`)

const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

function BandeauNonSimule({ avertissements }) {
  const raison = avertissements?.[0]
    || 'Calepinage non simulé : aucune valeur de production n\'a encore été calculée.'
  return (
    <div
      className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm"
      data-testid="cal236-non-simule"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
      <span>{raison}</span>
    </div>
  )
}

function BlocBase({ base }) {
  if (!base) return null
  return (
    <p className="text-xs text-muted-foreground" data-testid="cal236-base">
      Base {base.source || 'non calculée'}
      {base.fenetre_annees ? ` · fenêtre ${base.fenetre_annees}` : ''}
      {base.loss_passee_pct != null
        ? ` · pertes passées à PVGIS : ${formatPercent(base.loss_passee_pct, { decimals: 1 })}`
        : ''}
    </p>
  )
}

function TotalKpis({ total }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="cal236-total">
      <Stat label="P50 (annuel)" value={kwh(total?.p50_kwh)} />
      <Stat label="P75 (annuel)" value={kwh(total?.p75_kwh)} />
      <Stat label="P90 (annuel)" value={kwh(total?.p90_kwh)} />
      <Stat
        label="Variabilité annuelle (σ)"
        value={nonCalculee(total?.annual_variability,
          (x) => formatPercent(x * 100, { decimals: 1 }))}
      />
      <Stat label="Ratio de performance (PR)" value={pourcentagePerf(total?.performance_ratio)} />
      <Stat label="Productible" value={kwhParKwc(total?.specific_yield_kwh_kwc)} />
      <Stat label="Puissance installée" value={nonCalculee(total?.kwc,
        (x) => `${formatNumber(x, { decimals: 2 })} kWc`)}
      />
      <Stat label="Pertes totales" value={nonCalculee(total?.total_loss_pct,
        (x) => formatPercent(x, { decimals: 1 }))}
      />
    </div>
  )
}

function TableauMensuel({ mensuel }) {
  if (!mensuel?.length) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="cal236-mensuel-vide">
        Production mensuelle non calculée.
      </p>
    )
  }
  return (
    <table className="w-full text-sm" data-testid="cal236-mensuel">
      <thead>
        <tr className="text-left text-xs text-muted-foreground">
          <th className="py-1 font-normal">Mois</th>
          <th className="py-1 text-right font-normal">P50</th>
        </tr>
      </thead>
      <tbody>
        {mensuel.map((point) => (
          <tr key={point.mois} className="border-t border-border/60">
            <td className="py-1">{MOIS[(point.mois || 1) - 1] || point.mois}</td>
            <td className="py-1 text-right tabular-nums">{kwh(point.p50_kwh)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function TableauParPan({ parPan }) {
  if (!parPan?.length) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="cal236-par-pan-vide">
        Aucun pan.
      </p>
    )
  }
  return (
    <table className="w-full text-sm" data-testid="cal236-par-pan">
      <thead>
        <tr className="text-left text-xs text-muted-foreground">
          <th className="py-1 font-normal">Pan</th>
          <th className="py-1 text-right font-normal">Modules</th>
          <th className="py-1 text-right font-normal">kWc</th>
          <th className="py-1 text-right font-normal">P50</th>
          <th className="py-1 text-right font-normal">P75</th>
          <th className="py-1 text-right font-normal">P90</th>
          <th className="py-1 text-right font-normal">PR</th>
          <th className="py-1 text-right font-normal">kWh/kWc</th>
        </tr>
      </thead>
      <tbody>
        {parPan.map((pan) => (
          <tr key={pan.pan} className="border-t border-border/60">
            <td className="py-1">{pan.pan}</td>
            {/* Un pan sans module reste un vrai `0`, jamais « non calculée » :
                `formatNumber(0)` rend « 0 », distinct de `null`. */}
            <td className="py-1 text-right tabular-nums">{formatNumber(pan.modules, { decimals: 0 })}</td>
            <td className="py-1 text-right tabular-nums">
              {nonCalculee(pan.kwc, (x) => formatNumber(x, { decimals: 2 }))}
            </td>
            <td className="py-1 text-right tabular-nums">{kwh(pan.p50_kwh)}</td>
            <td className="py-1 text-right tabular-nums">{kwh(pan.p75_kwh)}</td>
            <td className="py-1 text-right tabular-nums">{kwh(pan.p90_kwh)}</td>
            <td className="py-1 text-right tabular-nums">{pourcentagePerf(pan.performance_ratio)}</td>
            <td className="py-1 text-right tabular-nums">{kwhParKwc(pan.specific_yield_kwh_kwc)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function PanneauProduction({ calepinageId }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data, loading, error } = useResource(
    () => calepinageApi.calepinages.resultat(id), id,
    { select: (r) => r.data, errorMessage: 'Production indisponible.' },
  )

  if (loading) return <Spinner />
  if (error) {
    return <p className="text-sm text-destructive" data-testid="cal236-erreur">{error}</p>
  }

  const production = data?.production || null

  return (
    <Card className="flex flex-col gap-4 p-4" data-testid="cal236-panneau">
      <h2 className="text-base font-semibold">Production</h2>
      {!data?.simule && <BandeauNonSimule avertissements={data?.avertissements} />}
      <BlocBase base={production?.base} />
      <TotalKpis total={production?.total} />
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Production mensuelle</p>
          <TableauMensuel mensuel={production?.mensuel} />
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Par pan</p>
          <TableauParPan parPan={production?.par_pan} />
        </div>
      </div>
    </Card>
  )
}
