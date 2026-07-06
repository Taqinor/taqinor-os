import {
  AreaChart, Area, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import {
  CHART_TOKENS, resolveColor, animationDuration, CHART_ANIM_EASING, ChartTooltip,
} from '../../../ui/charts'
import { formatNumber } from '../../../lib/format'

/* XPRJ17 — Burndown : charge restante RÉELLE vs ligne idéale, sur la même
   échelle temporelle (deux séries superposées). Réutilise le thème du kit
   graphique (tokens marque) — pas de couleur en dur, animation respectant
   prefers-reduced-motion. */

export default function BurndownChart({ points = [], height = 260 }) {
  const dur = animationDuration()
  const colorReel = resolveColor('primary')
  const colorIdeal = resolveColor('muted')

  const data = points.map((p) => ({
    date: p.date,
    'Charge restante': Number(p.charge_restante ?? 0),
    'Ligne idéale': Number(p.charge_ideale ?? 0),
  }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis hide domain={[0, 'auto']} />
        <Tooltip
          cursor={{ stroke: CHART_TOKENS.grid }}
          content={<ChartTooltip format={(v) => `${formatNumber(v)} h`} />}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area
          type="monotone"
          dataKey="Ligne idéale"
          stroke={colorIdeal}
          strokeDasharray="4 4"
          fill="none"
          dot={false}
          isAnimationActive={dur > 0}
          animationDuration={dur}
          animationEasing={CHART_ANIM_EASING}
        />
        <Area
          type="monotone"
          dataKey="Charge restante"
          stroke={colorReel}
          strokeWidth={2}
          fill={colorReel}
          fillOpacity={0.15}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 0 }}
          isAnimationActive={dur > 0}
          animationDuration={dur}
          animationEasing={CHART_ANIM_EASING}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
