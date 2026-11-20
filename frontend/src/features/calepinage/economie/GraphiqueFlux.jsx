import {
  Bar, Cell, ComposedChart, CartesianGrid, Line, ReferenceLine, ResponsiveContainer, XAxis, YAxis,
} from 'recharts'
import { formatMAD } from '../../../lib/format'
import { ChartFrame } from '../../../ui/charts'
import { CHART_GRID_STYLE, CHART_TOKENS, CHART_REFERENCE_LINE_STYLE } from '../../../ui/charts/chart-theme.js'

/* ACAL448 — le flux de trésorerie année par année : barres `flux_mad`, courbe
   `cumul_mad`, repère à `retour_ans`. AUCUN calcul monétaire : chaque valeur
   est une clé servie par ventes ; une valeur `null` reste `null` (trou : ni
   barre ni point), jamais 0. Flux vide ⇒ aucun graphique (le motif vit dans
   `omissions[]`, lu par la table). */
const axeMAD = (v) => formatMAD(v, { decimals: 0 })

export default function GraphiqueFlux({ flux, retourAns = null }) {
  if (!flux?.length) return null
  const donnees = flux.map((l) => ({
    annee: l.annee,
    flux: l.flux_mad ?? null,
    cumul: l.cumul_mad ?? null,
  }))
  const repere = typeof retourAns === 'number' && donnees.some((d) => d.annee === retourAns)
  return (
    <div data-testid="acal448-graphique">
      <ChartFrame label="Flux de trésorerie par année, avec le cumul et le retour sur investissement">
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={donnees} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid {...CHART_GRID_STYLE} />
            <XAxis dataKey="annee" tick={{ fontSize: 11, fill: CHART_TOKENS.axis }} tickLine={false} />
            <YAxis
              tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
              tickLine={false}
              axisLine={false}
              tickFormatter={axeMAD}
              width={90}
            />
            <Bar dataKey="flux" name="Flux" isAnimationActive={false}>
              {donnees.map((d) => (
                <Cell key={d.annee} fill={d.flux !== null && d.flux < 0 ? CHART_TOKENS.danger : CHART_TOKENS.primary} />
              ))}
            </Bar>
            <Line
              dataKey="cumul"
              name="Cumul"
              type="monotone"
              stroke={CHART_TOKENS.warning}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            {repere && (
              <ReferenceLine
                x={retourAns}
                {...CHART_REFERENCE_LINE_STYLE}
                label={{ value: `Retour : ${retourAns} ans`, fontSize: 11, fill: CHART_TOKENS.axis }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </ChartFrame>
    </div>
  )
}
