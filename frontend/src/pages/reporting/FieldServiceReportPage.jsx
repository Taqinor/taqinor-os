import { AlertOctagon, Gauge, RotateCcw, Timer } from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import { EmptyState } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { Table } from './Table'
import KpiCard from './KpiCard'
import { useChargementRapport } from './useChargementRapport'
import { ChargementPage } from '../../ui/ChargementPage'

/* ============================================================================
   XFSM16 — Analytics field service consolidés (`reporting/reports/field/`).
   ----------------------------------------------------------------------------
   First-time-fix, MTTR, ponctualité, récidive, temps trajet vs sur site,
   interventions par type/statut. Lecture seule, réservé responsable/admin.
   ========================================================================== */

const pct = (v) => (v == null ? '—' : `${v} %`)
const jours = (v) => (v == null ? '—' : `${v} j`)
const min = (v) => (v == null ? '—' : `${v} min`)

export default function FieldServiceReportPage() {
  const { data, loading, error } = useChargementRapport(reportingApi.fieldServiceReport)

  return (
    <div className="page">
      <PageHeader
        title="Analytics terrain"
        subtitle="First-time-fix, MTTR, ponctualité, récidive, trajet vs sur site — consolidés par technicien."
      />

      {loading ? (
        <ChargementPage />
      ) : error || !data ? (
        <EmptyState icon={AlertOctagon} title="Erreur" description="Impossible de charger les analytics terrain." className="my-6" />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap gap-3">
            <KpiCard icon={<Gauge />} label="Interventions" value={data.total_interventions} />
            <KpiCard icon={<Gauge />} label="% First-time-fix" value={pct(data.first_time_fix?.pct_ftf)} />
            <KpiCard icon={<Timer />} label="MTTR moyen" value={jours(data.mttr_jours_moyen)} />
            <KpiCard icon={<Gauge />} label="% ponctualité" value={pct(data.ponctualite?.taux_pct)} />
            <KpiCard icon={<RotateCcw />} label="% récidive" value={pct(data.recidive?.taux_pct)} />
            <KpiCard icon={<Timer />} label="Trajet moyen" value={min(data.temps_trajet_vs_site?.trajet_moyen_min)} />
            <KpiCard icon={<Timer />} label="Durée sur site moy." value={min(data.temps_trajet_vs_site?.duree_sur_site_moyenne_min)} />
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold">Par technicien</h3>
            <Table
              aria-label="Analytics field service par technicien"
              columns={[
                { key: 'technicien', header: 'Technicien' },
                { key: 'total_tickets', header: 'Tickets', align: 'right' },
                { key: 'ftf', header: '% FTF', align: 'right', cell: (r) => pct(r.pct_ftf) },
                { key: 'mttr', header: 'MTTR (j)', align: 'right', cell: (r) => jours(r.mttr_jours) },
                { key: 'recidive', header: '% récidive', align: 'right', cell: (r) => pct(r.taux_recidive_pct) },
                { key: 'trajet', header: 'Trajet moy.', align: 'right', cell: (r) => min(r.trajet_moyen_min) },
                { key: 'sursite', header: 'Sur site moy.', align: 'right', cell: (r) => min(r.duree_sur_site_moyenne_min) },
              ]}
              rows={data.par_technicien || []}
              getRowKey={(r) => r.technicien_id ?? r.technicien}
              empty={<p className="text-sm text-muted-foreground">Aucune intervention sur la période.</p>}
            />
          </div>
        </div>
      )}
    </div>
  )
}
