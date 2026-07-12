import { CHART_TOKENS } from './chart-theme.js'

/* K147 — Infobulle tokenisée du kit graphique. `format(value, name, entry)`
   optionnel pour formater la valeur (montants/%/etc.) ; sinon valeur brute. */
export function ChartTooltip({ active, payload, label, format, labelFormatter }) {
  if (!active || !payload?.length) return null
  const heading = labelFormatter ? labelFormatter(label) : label
  return (
    <div
      className="rounded-md border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-ui-md"
      role="tooltip"
    >
      {heading != null && heading !== '' && (
        <div className="mb-1 font-semibold">{heading}</div>
      )}
      {payload.map((p, i) => (
        <div
          key={i}
          className="flex items-center gap-1.5 tabular-nums"
          style={{ color: p.color ?? p.payload?.color ?? CHART_TOKENS.info }}
        >
          <span
            aria-hidden="true"
            className="inline-block size-2 shrink-0 rounded-[2px]"
            style={{ background: p.color ?? p.payload?.color ?? CHART_TOKENS.info }}
          />
          <span className="text-muted-foreground">{p.name}</span>
          <span className="ml-auto pl-2 font-semibold text-foreground">
            {format ? format(p.value, p.name, p) : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export default ChartTooltip
