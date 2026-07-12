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
import { BarChart3 } from 'lucide-react'
import {
  groupLeadsByStage,
  STAGE_COLORS,
  formatMAD,
} from '../../../../features/crm/stages'
import useCanaux from '../../../../features/crm/useCanaux'
import CrmInsightsPanel from '../CrmInsightsPanel'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, EmptyState, Button,
} from '../../../../ui'

// VX26 — navy/or dérivés des tokens de marque unifiés (VX1, tokens.css)
// plutôt que du hex local recharts.
const NAVY = 'var(--cat-navy)'
const GOLD = 'var(--cat-gold)'
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
const pctFormatter = (value) => [`${value} %`, 'Conversion']

export default function ChartsView({
  leads, totalLeads = null, onClearFilters,
}) {
  const isMobile = useIsMobile()
  // Libellés de canaux depuis le référentiel géré (Paramètres → CRM) + statiques.
  const { labels: canalLabels } = useCanaux()

  // Les 6 étapes canoniques, toujours dans l'ordre de l'entonnoir (même vides).
  const stageData = useMemo(() => groupLeadsByStage(leads ?? []), [leads])
  const totalDevis = useMemo(
    () => stageData.reduce((s, col) => s + col.totalDevis, 0),
    [stageData],
  )

  // Taux de conversion par étape (entonnoir) : part des leads ayant ATTEINT
  // l'étape e ou au-delà, rapportée au total. Donne un % décroissant le long
  // de l'entonnoir, indépendant du total des devis.
  const conversionData = useMemo(() => {
    const total = (leads ?? []).length
    if (!total) return stageData.map((col) => ({ ...col, rate: 0 }))
    let cumulRest = total
    const out = []
    for (const col of stageData) {
      const rate = Math.round((cumulRest / total) * 100)
      out.push({ key: col.key, label: col.label, rate })
      cumulRest -= col.count
    }
    return out
  }, [stageData, leads])

  // Comptes par responsable, « Non assigné » pour les leads sans owner_nom.
  const ownerData = useMemo(() => {
    const counts = new Map()
    for (const l of leads ?? []) {
      const key = l?.owner_nom || '__none'
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
    return [...counts.entries()]
      .map(([key, count]) => ({
        label: key === '__none' ? 'Non assigné' : key,
        count,
      }))
      .sort((a, b) => b.count - a.count)
  }, [leads])

  // Comptes par canal, libellés français, canal inconnu/vide → « Non renseigné ».
  const canalData = useMemo(() => {
    const counts = new Map()
    for (const l of leads ?? []) {
      const key = l?.canal && canalLabels[l.canal] ? l.canal : '__inconnu'
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
    return [...counts.entries()]
      .map(([key, count]) => ({
        label: key === '__inconnu' ? 'Non renseigné' : canalLabels[key],
        count,
      }))
      .sort((a, b) => b.count - a.count)
  }, [leads, canalLabels])

  if (!leads || leads.length === 0) {
    // Distingue « aucun lead du tout » de « aucun résultat pour ces filtres ».
    const aucunDuTout = totalLeads != null && totalLeads === 0
    if (aucunDuTout) {
      // VX40 — pictogramme solaire illustré (l'un des 4-5 écrans les plus
      // vus) : réservé au vrai « aucun lead du tout », jamais au cas
      // « filtres sans résultat » ci-dessous (routine, pas de délice).
      return (
        <EmptyState
          illustrated
          title="Aucune donnée à représenter"
          description="Aucun lead — créez votre premier lead"
        />
      )
    }
    return (
      <EmptyState
        icon={BarChart3}
        title="Aucune donnée à représenter"
        description="Aucun résultat pour ces filtres"
        action={onClearFilters ? (
          <Button type="button" variant="outline" size="sm" onClick={onClearFilters}>
            Effacer les filtres
          </Button>
        ) : null}
      />
    )
  }

  const xAxisProps = isMobile
    ? { interval: 0, angle: -25, textAnchor: 'end', height: 60 }
    : { interval: 0 }
  const chartMargin = isMobile
    ? { top: 8, right: 8, bottom: 24, left: 0 }
    : { top: 8, right: 8, bottom: 4, left: 0 }

  return (
    <>
    <div className="ch-grid">
      <Card className="ch-card ch-card-wide">
        <CardHeader>
          <CardTitle>Leads par étape</CardTitle>
          {totalDevis > 0 && (
            <CardDescription>Devis récents : {formatMAD(totalDevis)}</CardDescription>
          )}
        </CardHeader>
        <CardContent className="ch-chartbox">
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
        </CardContent>
      </Card>

      <Card className="ch-card">
        <CardHeader>
          <CardTitle>Leads par canal</CardTitle>
        </CardHeader>
        <CardContent className="ch-chartbox">
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
        </CardContent>
      </Card>

      <Card className="ch-card">
        <CardHeader>
          <CardTitle>Leads par responsable</CardTitle>
        </CardHeader>
        <CardContent className="ch-chartbox">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={ownerData} margin={chartMargin}>
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
                {ownerData.map((row, i) => (
                  <Cell key={row.label} fill={i === 0 ? GOLD : NAVY} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="ch-card">
        <CardHeader>
          <CardTitle>Taux de conversion par étape</CardTitle>
          <CardDescription>Part des leads ayant atteint chaque étape</CardDescription>
        </CardHeader>
        <CardContent className="ch-chartbox">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={conversionData} margin={chartMargin}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 12, fill: '#475569' }}
                tickLine={false}
                {...xAxisProps}
              />
              <YAxis
                allowDecimals={false}
                width={40}
                domain={[0, 100]}
                unit="%"
                tick={{ fontSize: 12, fill: '#475569' }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={pctFormatter}
                cursor={{ fill: 'rgba(15, 23, 42, 0.04)' }}
              />
              <Bar dataKey="rate" radius={[6, 6, 0, 0]} isAnimationActive={false}>
                {conversionData.map((col) => (
                  <Cell key={col.key} fill={STAGE_COLORS[col.key]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
    {/* WR9 — surfaces consultatives : objectifs, ROI par source, SLA. */}
    <CrmInsightsPanel />
    </>
  )
}
