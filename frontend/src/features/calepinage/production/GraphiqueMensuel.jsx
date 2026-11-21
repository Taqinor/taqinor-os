import {
  Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis,
} from 'recharts'
import { formatNumber } from '../../../lib/format'
import { ChartEmpty, ChartFrame, ChartTooltip } from '../../../ui/charts'
import {
  CHART_GRID_STYLE, CHART_TOKENS, animationDuration,
} from '../../../ui/charts/chart-theme.js'

/* ACAL453 — GRAPHIQUE MENSUEL Production / Consommation / Autoconsommée.
   Données SERVIES : `autoconsommation.par_mois` du résultat (ACAL445). Aucun
   calcul ; un mois `null` n'a pas de barre (jamais 0). Bloc ou `par_mois`
   absent : `ChartEmpty` qui nomme le `motif_absence` servi. */

const MOIS_COURT = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']

const kwhOuNonCalcule = (v) => (v === null || v === undefined
  ? 'non calculée' : `${formatNumber(v, { decimals: 0 })} kWh`)

export default function GraphiqueMensuel({ autoconsommation }) {
  const parMois = autoconsommation?.par_mois
  if (!Array.isArray(parMois) || !parMois.length) {
    return (
      <div data-testid="acal453-vide">
        <ChartEmpty
          title="Graphique mensuel indisponible"
          description={autoconsommation?.motif_absence
            || 'Consommation et autoconsommation non calculées.'}
        />
      </div>
    )
  }
  const donnees = parMois.map((m) => ({
    mois: MOIS_COURT[(m.mois || 1) - 1] || m.mois,
    production: m.production_kwh ?? null,
    consommation: m.consommation_kwh ?? null,
    autoconsommee: m.autoconsomme_kwh ?? null,
  }))
  const dur = animationDuration()
  return (
    <div data-testid="acal453-graphique">
      <ChartFrame
        label="Production, consommation et énergie autoconsommée par mois"
        columns={[
          { key: 'mois', header: 'Mois' },
          { key: 'production', header: 'Production (au compteur)', align: 'right', format: kwhOuNonCalcule },
          { key: 'consommation', header: 'Consommation', align: 'right', format: kwhOuNonCalcule },
          { key: 'autoconsommee', header: 'Autoconsommée', align: 'right', format: kwhOuNonCalcule },
        ]}
        rows={donnees}
        getRowKey={(row) => row.mois}
      >
        <BarChart
          width={640}
          height={240}
          data={donnees}
          margin={{ top: 8, right: 8, bottom: 8, left: 0 }}
        >
          <CartesianGrid {...CHART_GRID_STYLE} />
          <XAxis dataKey="mois" tick={{ fontSize: 11, fill: CHART_TOKENS.axis }} tickLine={false} />
          <YAxis
            tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
            tickLine={false}
            axisLine={false}
            unit=" kWh"
          />
          <Tooltip content={<ChartTooltip format={(v) => kwhOuNonCalcule(v)} />} />
          <Legend />
          <Bar dataKey="production" name="Production (au compteur)"
            fill={CHART_TOKENS.primary} isAnimationActive={dur > 0} animationDuration={dur} />
          <Bar dataKey="consommation" name="Consommation"
            fill={CHART_TOKENS.warning} isAnimationActive={dur > 0} animationDuration={dur} />
          <Bar dataKey="autoconsommee" name="Autoconsommée"
            fill={CHART_TOKENS.success} isAnimationActive={dur > 0} animationDuration={dur} />
        </BarChart>
      </ChartFrame>
    </div>
  )
}
