import { useId } from 'react'
import { AreaChart, Area, ResponsiveContainer, YAxis } from 'recharts'
import {
  resolveColor, animationDuration, CHART_ANIM_EASING,
} from './chart-theme.js'

/* K147 — Sparkline compacte pour cartes KPI : mini-aire sans axe ni infobulle,
   dégradé doux, trait fin. Décoratif → `aria-hidden`. Anim ~600 ms ease-out
   respectant `prefers-reduced-motion`.

   Props :
     data    : number[]  OU  [{ [dataKey]: number }]
     dataKey : clé si data est une liste d'objets (défaut 'value')
     tone    : couleur (défaut 'primary')
     height  : défaut 40
     strokeWidth : défaut 2
*/
export function KpiSpark({
  data = [],
  dataKey = 'value',
  tone = 'primary',
  height = 40,
  strokeWidth = 2,
}) {
  const gid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const color = resolveColor(tone)
  const dur = animationDuration()

  // Normalise number[] → [{ value }] pour recharts.
  const rows = data.map((d) =>
    (typeof d === 'number' ? { [dataKey]: d } : d),
  )

  if (rows.length === 0) return null

  return (
    <div aria-hidden="true" className="w-full">
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={rows} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`spark-${gid}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={['dataMin', 'dataMax']} />
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={strokeWidth}
            fill={`url(#spark-${gid})`}
            dot={false}
            isAnimationActive={dur > 0}
            animationDuration={dur}
            animationEasing={CHART_ANIM_EASING}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export default KpiSpark
