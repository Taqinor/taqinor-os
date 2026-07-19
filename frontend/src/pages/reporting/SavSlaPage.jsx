import { useEffect, useState } from 'react'
import { AlertOctagon, Clock, ShieldCheck } from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import { Badge, Card, CardContent, EmptyState, Spinner } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { Table } from './Table'

/* ============================================================================
   XSAV8 — Rapport de conformité SLA + KPI SAV avancés
   (`reporting/insights/sav-sla/`).
   ----------------------------------------------------------------------------
   % 1ère réponse / résolution dans les délais (par priorité et par
   technicien), délais moyens, backlog vieilli, % préventif vs correctif,
   ponctualité des visites préventives, taux de réouverture. Lecture seule,
   réservé responsable/admin. ========================================================================== */

const pct = (v) => (v == null ? '—' : `${v} %`)
const jours = (v) => (v == null ? '—' : `${v} j`)

function KpiCard({ icon, label, value }) {
  return (
    <Card className="flex-1 min-w-[160px]">
      <CardContent className="flex items-center gap-3 p-4">
        <div className="text-muted-foreground">{icon}</div>
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="text-lg font-semibold">{value}</div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function SavSlaPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // WIR102 — analytique SAV : taux d'attache, pivot tickets, coût moyen.
  const [tauxAttache, setTauxAttache] = useState(null)
  const [pivot, setPivot] = useState(null)
  const [coutMoyen, setCoutMoyen] = useState(null)

  useEffect(() => {
    let active = true
    reportingApi.savSlaInsight()
      .then((r) => { if (active) { setData(r.data); setError(false) } })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    // WIR102 — chargés en parallèle, best-effort (une source en erreur
    // n'empêche pas les autres de s'afficher ; le coût moyen est
    // permission-gated côté serveur : un 403 laisse simplement la carte cachée).
    reportingApi.savTauxAttache()
      .then((r) => { if (active) setTauxAttache(r.data) })
      .catch(() => { if (active) setTauxAttache(null) })
    reportingApi.savTicketsPivot()
      .then((r) => { if (active) setPivot(r.data) })
      .catch(() => { if (active) setPivot(null) })
    reportingApi.savTicketsCoutMoyen()
      .then((r) => { if (active) setCoutMoyen(r.data?.rows || []) })
      .catch(() => { if (active) setCoutMoyen(null) })
    return () => { active = false }
  }, [])

  return (
    <div className="page">
      <PageHeader
        title="SLA SAV"
        subtitle="Conformité SLA (1ère réponse / résolution), backlog vieilli, préventif vs correctif, ponctualité, réouvertures."
      />

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : error || !data ? (
        <EmptyState icon={AlertOctagon} title="Erreur" description="Impossible de charger le rapport SLA SAV." className="my-6" />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap gap-3">
            <KpiCard icon={<ShieldCheck />} label="Total tickets" value={data.total_tickets} />
            <KpiCard icon={<Clock />} label="Délai moyen 1ère réponse" value={jours(data.delai_moyen_premiere_reponse_jours)} />
            <KpiCard icon={<Clock />} label="Délai moyen résolution" value={jours(data.delai_moyen_resolution_jours)} />
            <KpiCard icon={<ShieldCheck />} label="% préventif" value={pct(data.preventif_vs_correctif?.pct_preventif)} />
            <KpiCard icon={<ShieldCheck />} label="Visites préventives à l’heure" value={pct(data.visites_preventives?.pct_a_heure)} />
            {data.reouverture && (
              <KpiCard icon={<AlertOctagon />} label="Réouvertures / 100 tickets" value={data.reouverture.taux_pour_100_tickets} />
            )}
            {/* WIR102 — taux d'attache contrat (YSERV10). */}
            {tauxAttache && (
              <KpiCard
                icon={<ShieldCheck />}
                label="Taux d’attache contrat"
                value={`${pct(tauxAttache.taux_pct)} (${tauxAttache.avec_contrat}/${tauxAttache.total})`}
              />
            )}
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold">Backlog vieilli (tickets ouverts)</h3>
            <div className="flex flex-wrap gap-3">
              <Badge tone="neutral">0-2 j : {data.backlog_vieilli?.buckets?.['0_2j'] ?? 0}</Badge>
              <Badge tone="warning">3-7 j : {data.backlog_vieilli?.buckets?.['3_7j'] ?? 0}</Badge>
              <Badge tone="danger">+7 j : {data.backlog_vieilli?.buckets?.plus_7j ?? 0}</Badge>
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold">Conformité SLA par priorité</h3>
            <Table
              aria-label="Conformité SLA par priorité"
              columns={[
                { key: 'label', header: 'Priorité' },
                { key: 'total', header: 'Total', align: 'right' },
                { key: 'reponse', header: '% 1ère réponse OK', align: 'right', cell: (r) => pct(r.pct_premiere_reponse_ok) },
                { key: 'resolution', header: '% résolution OK', align: 'right', cell: (r) => pct(r.pct_resolution_ok) },
              ]}
              rows={data.par_priorite || []}
              getRowKey={(r) => r.priorite}
              empty={<p className="text-sm text-muted-foreground">Aucun ticket sur la période.</p>}
            />
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold">Conformité SLA par technicien</h3>
            <Table
              aria-label="Conformité SLA par technicien"
              columns={[
                { key: 'technicien', header: 'Technicien' },
                { key: 'total', header: 'Total', align: 'right' },
                { key: 'reponse', header: '% 1ère réponse OK', align: 'right', cell: (r) => pct(r.pct_premiere_reponse_ok) },
                { key: 'resolution', header: '% résolution OK', align: 'right', cell: (r) => pct(r.pct_resolution_ok) },
                { key: 'reouvertures', header: 'Réouvertures', align: 'right', cell: (r) => r.reouvertures ?? 0 },
              ]}
              rows={data.par_technicien || []}
              getRowKey={(r) => r.technicien_id ?? r.technicien}
              empty={<p className="text-sm text-muted-foreground">Aucun ticket sur la période.</p>}
            />
          </div>

          {/* WIR102 — pivot tickets SAV (technicien × statut). */}
          {pivot && (pivot.row_keys || []).length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Tickets par technicien et statut</h3>
              <Table
                aria-label="Pivot tickets SAV par technicien et statut"
                columns={[
                  { key: 'technicien', header: 'Technicien', cell: (r) => r.label },
                  ...(pivot.col_keys || []).map((ck) => {
                    const ckKey = ck.join(',')
                    return {
                      key: `col_${ckKey}`,
                      header: ckKey || '—',
                      align: 'right',
                      cell: (r) => r.cells[ckKey] ?? 0,
                    }
                  }),
                  { key: 'total', header: 'Total', align: 'right', cell: (r) => r.total },
                ]}
                rows={(pivot.row_keys || []).map((rk) => {
                  const rowKey = rk.join(',')
                  return {
                    id: rowKey,
                    label: rowKey || '—',
                    cells: pivot.cells?.[rowKey] || {},
                    total: pivot.row_totals?.[rowKey] ?? 0,
                  }
                })}
                getRowKey={(r) => r.id}
                empty={<p className="text-sm text-muted-foreground">Aucun ticket sur la période.</p>}
              />
            </div>
          )}

          {/* WIR102 — coût interne moyen par technicien (permission prix_achat_voir ;
              masqué sans elle, le serveur renvoyant 403). */}
          {coutMoyen && coutMoyen.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Coût interne moyen par technicien</h3>
              <Table
                aria-label="Coût interne moyen par technicien"
                columns={[
                  { key: 'technicien', header: 'Technicien', cell: (r) => r.technicien_responsable__username || '—' },
                  { key: 'cout_moyen', header: 'Coût moyen', align: 'right', cell: (r) => (r.cout_moyen != null ? Math.round(r.cout_moyen) : '—') },
                  { key: 'n', header: 'Tickets', align: 'right', cell: (r) => r.n ?? 0 },
                ]}
                rows={coutMoyen}
                getRowKey={(r) => r.technicien_responsable__username || 'na'}
                empty={<p className="text-sm text-muted-foreground">Aucune donnée.</p>}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
