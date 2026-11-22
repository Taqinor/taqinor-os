import {
  Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis,
} from 'recharts'
import { formatNumber } from '../../../lib/format'
import { ChartEmpty, ChartFrame, ChartTooltip } from '../../../ui/charts'
import {
  CHART_GRID_STYLE, CHART_TOKENS, animationDuration,
} from '../../../ui/charts/chart-theme.js'

/* ACAL453 — GRAPHIQUE MENSUEL Production / Consommation / Autoconsommée.
   Données SERVIES : `autoconsommation.par_mois` (ACAL445), sinon `production.mensuel` (R3-08). Aucun
   calcul ; un mois `null` n'a pas de barre (jamais 0). Bloc ou `par_mois`
   absent : `ChartEmpty` qui nomme le `motif_absence` servi. */

const MOIS_COURT = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']

const kwhOuNonCalcule = (v) => (v === null || v === undefined
  ? 'non calculée' : `${formatNumber(v, { decimals: 0 })} kWh`)

export default function GraphiqueMensuel({ autoconsommation, production = null }) {
  const parMois = autoconsommation?.par_mois
  const avecCharge = Array.isArray(parMois) && parMois.length > 0
  const mensuel = Array.isArray(production?.mensuel) ? production.mensuel : []
  if (!avecCharge && !mensuel.length) {
    return (
      <div data-testid="acal453-vide">
        <ChartEmpty
          title="Graphique mensuel indisponible"
          description={autoconsommation?.motif_absence
            || 'Production, consommation et autoconsommation non calculées.'}
        />
      </div>
    )
  }
  /* R3-08 — la production mensuelle SERVIE se trace même sans consommation :
     le motif ne vaut que pour la consommation et l'autoconsommation. */
  const donnees = avecCharge ? parMois.map((m) => ({
    mois: MOIS_COURT[(m.mois || 1) - 1] || m.mois,
    production: m.production_kwh ?? null,
    consommation: m.consommation_kwh ?? null,
    autoconsommee: m.autoconsomme_kwh ?? null,
  })) : mensuel.map((m) => ({
    mois: MOIS_COURT[(m.mois || 1) - 1] || m.mois,
    production: m.p50_kwh ?? null,
  }))
  const dur = animationDuration()
  const nomProduction = avecCharge ? 'Production (au compteur)' : 'Production (P50)'
  return (
    <div data-testid="acal453-graphique">
      {!avecCharge && (
        <p className="mb-1 text-xs text-muted-foreground" data-testid="acal453-motif">
          {`Consommation et énergie autoconsommée non tracées : ${autoconsommation?.motif_absence
            || 'aucune consommation connue pour ce calepinage.'}`}
        </p>
      )}
      <ChartFrame
        label={avecCharge ? 'Production, consommation et énergie autoconsommée par mois'
          : 'Production par mois'}
        columns={[
          { key: 'mois', header: 'Mois' },
          { key: 'production', header: nomProduction, align: 'right', format: kwhOuNonCalcule },
          ...(avecCharge ? [
            { key: 'consommation', header: 'Consommation', align: 'right', format: kwhOuNonCalcule },
            { key: 'autoconsommee', header: 'Autoconsommée', align: 'right', format: kwhOuNonCalcule },
          ] : []),
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
          <Bar dataKey="production" name={nomProduction}
            fill={CHART_TOKENS.primary} isAnimationActive={dur > 0} animationDuration={dur} />
          {avecCharge && (
            <Bar dataKey="consommation" name="Consommation"
              fill={CHART_TOKENS.warning} isAnimationActive={dur > 0} animationDuration={dur} />
          )}
          {avecCharge && (
            <Bar dataKey="autoconsommee" name="Autoconsommée"
              fill={CHART_TOKENS.success} isAnimationActive={dur > 0} animationDuration={dur} />
          )}
        </BarChart>
      </ChartFrame>
    </div>
  )
}
