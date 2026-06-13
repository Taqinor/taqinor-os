import { useEffect, useMemo, useState } from 'react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import {
  groupLeadsByStage,
  STAGE_COLORS,
  CANAL_LABELS,
  formatMAD,
} from '../../../../features/crm/stages'
import './charts.css'

const NAVY = '#0b1f3a'
const GOLD = '#f5a623'
const MOBILE_QUERY = '(max-width: 768px)'

// Vrai sous 768px — pour incliner les libellés d'axe sur mobile.
function useIsMobile() {
  const [mobile, setMobile] = useState(
    () => window.matchMedia(MOBILE_QUERY).matches,
  )
  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY)
    const onChange = (e) => setMobile(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return mobile
}

const tooltipFormatter = (value) => [`${value}`, 'Leads']

export default function ChartsView({ leads }) {
  const isMobile = useIsMobile()

  // Les 6 étapes canoniques, toujours dans l'ordre de l'entonnoir (même vides).
  const stageData = useMemo(() => groupLeadsByStage(leads ?? []), [leads])
  const totalDevis = useMemo(
    () => stageData.reduce((s, col) => s + col.totalDevis, 0),
    [stageData],
  )

  // Comptes par canal, libellés français, canal inconnu/vide → « Non renseigné ».
  const canalData = useMemo(() => {
    const counts = new Map()
    for (const l of leads ?? []) {
      const key = l?.canal && CANAL_LABELS[l.canal] ? l.canal : '__inconnu'
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
    return [...counts.entries()]
      .map(([key, count]) => ({
        label: key === '__inconnu' ? 'Non renseigné' : CANAL_LABELS[key],
        count,
      }))
      .sort((a, b) => b.count - a.count)
  }, [leads])

  if (!leads || leads.length === 0) {
    return (
      <div className="ch-empty">
        Aucun lead à représenter avec ces filtres.
      </div>
    )
  }

  const xAxisProps = isMobile
    ? { interval: 0, angle: -25, textAnchor: 'end', height: 60 }
    : { interval: 0 }
  const chartMargin = isMobile
    ? { top: 8, right: 8, bottom: 24, left: 0 }
    : { top: 8, right: 8, bottom: 4, left: 0 }

  return (
    <div className="ch-grid">
      <section className="ch-card">
        <h3 className="ch-title">Leads par étape</h3>
        {totalDevis > 0 && (
          <p className="ch-subtitle">Devis récents : {formatMAD(totalDevis)}</p>
        )}
        <div className="ch-chartbox">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={stageData} margin={chartMargin}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 12, fill: '#475569' }}
                tickLine={false}
                {...xAxisProps}
              />
              <YAxis
                allowDecimals={false}
                width={32}
                tick={{ fontSize: 12, fill: '#475569' }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={tooltipFormatter}
                cursor={{ fill: 'rgba(15, 23, 42, 0.04)' }}
              />
              <Bar dataKey="count" radius={[6, 6, 0, 0]} isAnimationActive={false}>
                {stageData.map((col) => (
                  <Cell key={col.key} fill={STAGE_COLORS[col.key]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="ch-card">
        <h3 className="ch-title">Leads par canal</h3>
        <div className="ch-chartbox">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={canalData} margin={chartMargin}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 12, fill: '#475569' }}
                tickLine={false}
                {...xAxisProps}
              />
              <YAxis
                allowDecimals={false}
                width={32}
                tick={{ fontSize: 12, fill: '#475569' }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={tooltipFormatter}
                cursor={{ fill: 'rgba(15, 23, 42, 0.04)' }}
              />
              <Bar dataKey="count" radius={[6, 6, 0, 0]} isAnimationActive={false}>
                {canalData.map((row, i) => (
                  <Cell key={row.label} fill={i === 0 ? GOLD : NAVY} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  )
}
