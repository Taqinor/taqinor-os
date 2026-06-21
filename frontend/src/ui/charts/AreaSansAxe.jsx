import { useId } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  resolveColor, animationDuration, CHART_ANIM_EASING, CHART_TOKENS,
} from './chart-theme.js'
import { ChartTooltip } from './ChartTooltip.jsx'

/* K147 — Aire « sans axe » marque : pas de lignes d'axe ni de ticks visibles
   (axe désactivé), dégradé de remplissage (opacité ~0.3 → 0), trait
   `strokeWidth=2`, courbe `monotone`, animation ~600 ms ease-out respectant
   `prefers-reduced-motion`.

   Props :
     data        : [{ [xKey]: …, [dataKey]: number }]
     dataKey     : clé de la série (défaut 'value')
     xKey        : clé de l'axe X (défaut 'label')
     tone        : 'primary'|'info'|… ou couleur CSS brute (défaut 'info')
     height      : hauteur du conteneur (défaut 200)
     name        : libellé de la série (infobulle)
     tooltipFormat : (value, name, entry) => string
     showXAxis   : afficher les libellés X (sans ligne d'axe) — défaut true
     ...recharts margin overridable via `margin`
*/
export function AreaSansAxe({
  data = [],
  dataKey = 'value',
  xKey = 'label',
  tone = 'info',
  height = 200,
  name = '',
  tooltipFormat,
  showXAxis = true,
  margin = { top: 8, right: 8, bottom: 0, left: 0 },
}) {
  const gid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const color = resolveColor(tone)
  const dur = animationDuration()

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={margin}>
        <defs>
          <linearGradient id={`area-${gid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        {showXAxis && (
          <XAxis
            dataKey={xKey}
            tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
            tickLine={false}
            axisLine={false}
          />
        )}
        {/* Axe Y masqué (échelle conservée, aucune ligne/tick) — « sans axe ». */}
        <YAxis hide domain={[0, 'auto']} />
        <Tooltip
          cursor={{ stroke: CHART_TOKENS.grid }}
          content={<ChartTooltip format={tooltipFormat} />}
        />
        <Area
          type="monotone"
          dataKey={dataKey}
          name={name}
          stroke={color}
          strokeWidth={2}
          fill={`url(#area-${gid})`}
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

export default AreaSansAxe
