import { useMemo, useState } from 'react'
import { Fuel, Gauge, Leaf, PackageCheck, ShieldAlert } from 'lucide-react'

import api from '../../api/axios'
import useResource from '../../hooks/useResource'
import PageHeader from '../../components/layout/PageHeader'
import { Card, CardContent, CardHeader, CardTitle, Input, Label, Spinner } from '../../ui'
import { BarArrondie, ChartFrame } from '../../ui/charts'
import { formatMAD, formatNumber, formatPercent } from '../../lib/format'

/* ============================================================================
   NTLOG24 — Tableau de bord logistique (`/transport/tableau-bord`).
   ----------------------------------------------------------------------------
   Cartes KPI (coût/kg transporté, taux de service, litiges ouverts, CO2 total
   estimé) + répartition flotte propre/affrètement, sur
   `ordres-transport/tableau-bord-logistique/?periode=YYYY-MM`
   (`selectors.tableau_bord_logistique`). Le taux de service exclut toujours
   les ordres annulés (calculé côté serveur).
   ========================================================================== */

function KpiCard({ icon, label, value, hint }) {
  // Classe lint maison #23b : le rename de déstructuration (`icon: Icon`)
  // n'est pas crédité par no-unused-vars (cf. LeadsPage.jsx).
  const Icon = icon
  return (
    <Card>
      <CardContent className="flex items-start gap-3 pt-4 sm:pt-5">
        <div className="rounded-md bg-muted p-2">
          <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-muted-foreground">{label}</span>
          <span className="text-lg font-semibold tabular-nums">{value}</span>
          {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
        </div>
      </CardContent>
    </Card>
  )
}

function unwrap(res) {
  return res.data || null
}

export default function TableauBordLogistique() {
  const [periode, setPeriode] = useState('')

  const params = useMemo(
    () => (periode ? { periode } : {}),
    [periode],
  )
  const { data, loading, error } = useResource(
    () => api.get('/transport/ordres-transport/tableau-bord-logistique/', { params }),
    params,
    { initialData: null, select: unwrap },
  )

  const repartition = data?.repartition_mode_transport || {}
  const chartData = useMemo(() => ([
    { label: 'Flotte propre', value: repartition.flotte_propre || 0, color: 'info' },
    { label: 'Affrètement', value: repartition.affretement || 0, color: 'primary' },
  ]), [repartition.flotte_propre, repartition.affretement])

  return (
    <div className="page flex flex-col gap-4">
      <PageHeader
        title="Tableau de bord logistique"
        subtitle="Coût/kg transporté, taux de service, litiges ouverts et CO2 estimé — ordres annulés toujours exclus."
      />

      <div className="max-w-[180px]">
        <Label htmlFor="tbl-periode">Période</Label>
        <Input
          id="tbl-periode"
          type="month"
          value={periode}
          onChange={(e) => setPeriode(e.target.value)}
        />
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement…
        </div>
      ) : error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              icon={Fuel}
              label="Coût / kg transporté"
              value={data?.cout_par_kg_transporte != null
                ? formatMAD(data.cout_par_kg_transporte, { decimals: 2 })
                : '—'}
              hint={`${formatNumber(data?.poids_livre_kg ?? 0, { decimals: 0 })} kg livrés`}
            />
            <KpiCard
              icon={Gauge}
              label="Taux de service"
              value={data?.taux_service_pct != null ? formatPercent(data.taux_service_pct, { decimals: 1 }) : '—'}
              hint={`${data?.nb_livres ?? 0} ordre(s) livré(s)`}
            />
            <KpiCard
              icon={ShieldAlert}
              label="Litiges ouverts"
              value={data?.litiges_ouverts_count ?? 0}
              hint={formatMAD(data?.litiges_ouverts_montant_conteste ?? 0, { decimals: 0 })}
            />
            <KpiCard
              icon={Leaf}
              label="CO2 total estimé"
              value={`${formatNumber(data?.co2_total_estime_kg ?? 0, { decimals: 0 })} kg`}
              hint="Estimation indicative, non certifiée"
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PackageCheck className="size-4" aria-hidden="true" />
                Répartition flotte propre / affrètement
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ChartFrame
                label="Répartition des ordres de transport par mode : flotte propre vs affrètement"
                columns={[
                  { key: 'label', header: 'Mode' },
                  { key: 'value', header: 'Ordres', align: 'right' },
                ]}
                rows={chartData}
              >
                <BarArrondie data={chartData} dataKey="value" categoryKey="label" colorKey="color" height={220} />
              </ChartFrame>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
