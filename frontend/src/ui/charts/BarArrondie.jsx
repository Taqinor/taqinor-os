import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import {
  resolveColor, animationDuration, CHART_ANIM_EASING, CHART_TOKENS,
  BAR_RADIUS, BAR_RADIUS_H,
} from './chart-theme.js'
import { ChartTooltip } from './ChartTooltip.jsx'

/* K147 — Barres arrondies marque : coins arrondis (`radius=[4,4,0,0]`
   vertical / `[0,4,4,0]` horizontal), pas de lignes d'axe ni de ticks, anim
   ~600 ms ease-out respectant `prefers-reduced-motion`. Couleur par défaut, ou
   couleur par ligne via `row.color`/`colorKey`.

   Props :
     data        : [{ [categoryKey]: …, [dataKey]: number, color? }]
     dataKey     : clé numérique (défaut 'value')
     categoryKey : clé de catégorie (défaut 'label')
     tone        : couleur par défaut (défaut 'primary')
     colorKey    : clé éventuelle d'une couleur par ligne (défaut 'color')
     layout      : 'horizontal' (barres verticales) | 'vertical' (barres horizontales)
     height      : défaut 200
     barSize     : épaisseur de barre
     name        : libellé série (infobulle)
     tooltipFormat : (value, name, entry) => string
*/
export function BarArrondie({
  data = [],
  dataKey = 'value',
  categoryKey = 'label',
  tone = 'primary',
  colorKey = 'color',
  layout = 'horizontal',
  height = 200,
  barSize,
  name = '',
  tooltipFormat,
  categoryWidth = 90,
  margin = { top: 4, right: 8, bottom: 0, left: 0 },
}) {
  const color = resolveColor(tone)
  const dur = animationDuration()
  const horizontalBars = layout === 'vertical' // recharts: barres horizontales
  const radius = horizontalBars ? BAR_RADIUS_H : BAR_RADIUS

  const axisTick = { fontSize: 11, fill: CHART_TOKENS.axis }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout={layout} margin={margin}>
        {horizontalBars ? (
          <>
            <XAxis type="number" allowDecimals={false} tick={axisTick} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey={categoryKey} width={categoryWidth} tick={axisTick} tickLine={false} axisLine={false} />
          </>
        ) : (
          <>
            <XAxis dataKey={categoryKey} tick={axisTick} tickLine={false} axisLine={false} />
            <YAxis allowDecimals={false} hide />
          </>
        )}
        <Tooltip
          cursor={{ fill: 'var(--muted)' }}
          content={<ChartTooltip format={tooltipFormat} />}
        />
        <Bar
          dataKey={dataKey}
          name={name}
          fill={color}
          radius={radius}
          barSize={barSize}
          isAnimationActive={dur > 0}
          animationDuration={dur}
          animationEasing={CHART_ANIM_EASING}
        >
          {data.some((d) => d?.[colorKey])
            ? data.map((d, i) => (
              <Cell key={i} fill={resolveColor(d[colorKey]) ?? color} />
            ))
            : null}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export default BarArrondie
