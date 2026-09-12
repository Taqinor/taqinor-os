import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertOctagon, Clock, HardHat, ReceiptText, RotateCcw } from 'lucide-react'
import api from '../../api/axios'
import { Card, CardContent, EmptyState, Spinner } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { Table } from './Table'

/* ============================================================================
   CHT27 — Cockpit KPI chantier (`reporting/reports/chantier/`).
   ----------------------------------------------------------------------------
   INSTRUMENTÉ, pas déclaratif : cycle time par étape (dérivé du chatter
   `InstallationActivity`, jamais des dates milestone), taux de reprise
   post-mise en service (DISTINCT du taux de récidive SAV par ticket),
   chantiers en retard vs `date_pose_prevue`. La quatrième tuile (tranches à
   facturer en attente) réutilise l'endpoint existant `installations/
   chantiers/a-facturer/` (YSERV7) — zéro second backend créé ici.
   Réservé responsable/admin. AUCUN prix d'achat / marge d'achat affiché.
   ========================================================================== */

const jours = (v) => (v == null ? '—' : `${v} j`)
const pct = (v) => (v == null ? '—' : `${v} %`)

function KpiCard({ icon, label, value, sub }) {
  return (
    <Card className="flex-1 min-w-[200px]">
      <CardContent className="flex items-center gap-3 p-4">
        <div className="text-muted-foreground">{icon}</div>
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="text-lg font-semibold">{value}</div>
          {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
        </div>
      </CardContent>
    </Card>
  )
}

export default function PilotageChantiersPage() {
  const [report, setReport] = useState(null)
  const [aFacturer, setAFacturer] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([
      api.get('/reporting/reports/chantier/'),
      // YSERV7 — endpoint existant (installations), déjà utilisé par le
      // board ventes (CHT14) : simple second fetch, zéro backend nouveau ici.
      api.get('/installations/chantiers/a-facturer/').catch(() => ({ data: [] })),
    ])
      .then(([reportResp, facturerResp]) => {
        if (!active) return
        setReport(reportResp.data)
        setAFacturer(Array.isArray(facturerResp.data) ? facturerResp.data : [])
        setError(false)
      })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  return (
    <div className="page">
      <PageHeader
        title="Pilotage chantiers"
        subtitle="Cycle time par étape, taux de reprise post-mise en service, chantiers en retard, tranches à facturer en attente."
      />

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : error || !report ? (
        <EmptyState icon={AlertOctagon} title="Erreur" description="Impossible de charger le pilotage chantiers." className="my-6" />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap gap-3">
            <KpiCard
              icon={<RotateCcw />}
              label="Taux de reprise post-MES"
              value={pct(report.taux_reprise_post_mes?.taux_pct)}
              sub={`${report.taux_reprise_post_mes?.nb_avec_reprise ?? 0}/${report.taux_reprise_post_mes?.nb_eligibles ?? 0} chantiers · fenêtre ${report.taux_reprise_post_mes?.fenetre_jours ?? 30} j`}
            />
            <KpiCard
              icon={<Clock />}
              label="Chantiers en retard"
              value={report.chantiers_en_retard?.total ?? 0}
              sub="vs date de pose prévue"
            />
            <KpiCard
              icon={<ReceiptText />}
              label="Tranches à facturer en attente"
              value={aFacturer.length}
            />
          </div>

          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <HardHat size={16} /> Cycle par étape (jours, chantier signé → réceptionné)
            </h3>
            <Table
              aria-label="Cycle time chantier par étape"
              columns={[
                { key: 'label', header: 'Transition' },
                { key: 'n', header: 'Chantiers mesurés', align: 'right' },
                { key: 'median', header: 'Médiane', align: 'right', cell: (r) => jours(r.jours_median) },
                { key: 'moyen', header: 'Moyenne', align: 'right', cell: (r) => jours(r.jours_moyen) },
              ]}
              rows={report.cycle_time?.segments || []}
              getRowKey={(r) => `${r.de}-${r.vers}`}
              empty={<p className="text-sm text-muted-foreground">Aucune transition mesurable sur la période.</p>}
            />
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold">Chantiers en retard</h3>
            <Table
              aria-label="Chantiers en retard vs date de pose prévue"
              columns={[
                {
                  key: 'reference', header: 'Chantier',
                  cell: (r) => <Link to={`/chantiers?id=${r.installation_id}`}>{r.reference}</Link>,
                },
                { key: 'client', header: 'Client' },
                { key: 'date_pose_prevue', header: 'Pose prévue' },
                { key: 'jours_retard', header: 'Retard', align: 'right', cell: (r) => jours(r.jours_retard) },
              ]}
              rows={report.chantiers_en_retard?.items || []}
              getRowKey={(r) => r.installation_id}
              empty={<p className="text-sm text-muted-foreground">Aucun chantier en retard.</p>}
            />
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold">Tranches à facturer en attente</h3>
            <Table
              aria-label="Tranches à facturer en attente"
              columns={[
                {
                  key: 'reference', header: 'Chantier',
                  cell: (r) => <Link to={`/chantiers?id=${r.installation_id}`}>{r.reference}</Link>,
                },
                { key: 'jalon_libelle', header: 'Jalon' },
                { key: 'tranche', header: 'Tranche', align: 'right' },
              ]}
              rows={aFacturer}
              getRowKey={(r, i) => r.jalon_id ?? i}
              empty={<p className="text-sm text-muted-foreground">Aucune tranche en attente.</p>}
            />
          </div>
        </div>
      )}
    </div>
  )
}
