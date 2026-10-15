import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  CHART_TOKENS, CHART_GRID_STYLE, CHART_COMPARISON_STYLE, categoricalColor,
  animationDuration, CHART_ANIM_EASING,
} from './chart-theme.js'
import { ChartTooltip } from './ChartTooltip.jsx'
import { Segmented } from '../Segmented'

/* ENF19 — graphique « CA : période actuelle vs période précédente » (VX41),
   extrait à l'identique de pages/Dashboard.jsx et pages/Reporting.jsx où il
   était recopié. Série courante en trait plein (palette CA), précédente en
   pointillé (CHART_COMPARISON_STYLE) + légende claire (les couleurs recharts
   natives ne rendent pas le style pointillé). `data` porte `mois`, `ca` et
   `caPrecedent` ; `format` formate les montants du tooltip. */
export function CaCompareChart({ data, height, format }) {
  return (
    <>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid {...CHART_GRID_STYLE} />
          <XAxis
            dataKey="mois"
            tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis hide domain={[0, 'auto']} />
          <Tooltip
            cursor={{ stroke: CHART_TOKENS.grid }}
            content={<ChartTooltip format={format} />}
          />
          <Area
            type="monotone"
            dataKey="ca"
            name="CA HT (période actuelle)"
            stroke={categoricalColor(0)}
            strokeWidth={2}
            fill={categoricalColor(0)}
            fillOpacity={0.12}
            dot={false}
            isAnimationActive={animationDuration() > 0}
            animationDuration={animationDuration()}
            animationEasing={CHART_ANIM_EASING}
          />
          <Area
            type="monotone"
            dataKey="caPrecedent"
            name="CA HT (période précédente)"
            stroke={categoricalColor(1)}
            dot={false}
            isAnimationActive={animationDuration() > 0}
            animationDuration={animationDuration()}
            animationEasing={CHART_ANIM_EASING}
            {...CHART_COMPARISON_STYLE}
          />
        </AreaChart>
      </ResponsiveContainer>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-0.5 w-3.5 rounded-full" style={{ background: categoricalColor(0) }} />
          Période actuelle
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block h-0.5 w-3.5"
            style={{
              backgroundImage: `repeating-linear-gradient(90deg, ${categoricalColor(1)} 0 4px, transparent 4px 7px)`,
            }}
          />
          Période précédente
        </span>
      </div>
    </>
  )
}

// Bascule « CA seul » / « Vs période précédente » (VX41).
export function CaCompareToggle({ caCompare, setCaCompare }) {
  return (
    <Segmented
      size="sm"
      value={caCompare ? 'compare' : 'simple'}
      onChange={(v) => setCaCompare(v === 'compare')}
      options={[
        { value: 'simple', label: 'CA seul' },
        { value: 'compare', label: 'Vs période précédente' },
      ]}
    />
  )
}
