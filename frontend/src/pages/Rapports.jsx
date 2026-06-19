// T13/T14/T15 — Hub « Rapports » : ventes/pipeline, stock, service (chantier +
// SAV). Lecture seule ; chaque rapport est exportable en .xlsx. Données
// agrégées côté serveur, bornées à la société.
import { useCallback, useEffect, useState } from 'react'
import { Download, BarChart3 } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import api from '../api/axios'
import reportingApi from '../api/reportingApi'
import { downloadXlsx } from '../api/importApi'
import { formatNumber } from '../lib/format'
import {
  Button, Card, CardHeader, CardTitle, CardDescription, CardContent,
  Tabs, TabsList, TabsTrigger, TabsContent, Skeleton, EmptyState, Input,
} from '../ui'

const CHART_PRIMARY = 'var(--color-info)'
const CHART_GRID = 'var(--color-border)'
const CHART_AXIS = 'var(--color-muted-foreground)'

// Tableau de données restylé (conserve la classe sémantique .data-table).
// Enveloppé dans un conteneur scrollable horizontalement pour les tables
// multi-colonnes sur petits écrans.
//
// L882 — `footer` (optionnel) : un tableau de cellules de pied « Total » rendu
// dans un <tfoot>, calculé depuis les MÊMES données que les lignes. Masqué
// quand il n'y a aucune ligne.
function Table({ headers, rows, footer }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table mb-2">
        <thead><tr>{headers.map(h => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{r.map((c, j) => <td key={j} data-label={headers[j]}>{c}</td>)}</tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={headers.length} className="text-muted-foreground">Aucune donnée.</td>
            </tr>
          )}
        </tbody>
        {footer && rows.length > 0 && (
          <tfoot>
            <tr className="font-semibold">
              {footer.map((c, j) => (
                <td key={j} data-label={headers[j]}>{c}</td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}

// Somme d'une colonne numérique depuis les objets-source (pas les lignes déjà
// formatées) — base du pied « Total » L882.
const sumBy = (arr, key) => (arr || []).reduce((s, o) => s + Number(o[key] || 0), 0)

// Sous-titre interne d'une carte.
function Subhead({ children }) {
  return (
    <h4 className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h4>
  )
}

// Carte de rapport T13/T14/T15 (export Excel via le chemin /reports/<kind>/).
// `params` (période) est transmis à l'export pour qu'il honore le filtre.
function ReportCard({ title, kind, params, children }) {
  const onExport = () => api
    .get(`/reporting/reports/${kind}/`,
      { params: { ...(params || {}), export: 'xlsx' }, responseType: 'blob' })
    .then(r => downloadXlsx(r.data, `rapport-${kind}.xlsx`))
    .catch(() => {})
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <CardTitle>{title}</CardTitle>
        <Button variant="outline" size="sm" onClick={onExport}>
          <Download /> Exporter Excel
        </Button>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

// Carte « insight » avec un bouton d'export personnalisé (chemin différent des
// rapports T13/T14/T15). onExport optionnel : pas de bouton si absent.
function InsightCard({ title, note, onExport, children }) {
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="space-y-1">
          <CardTitle>{title}</CardTitle>
          {note && <CardDescription>{note}</CardDescription>}
        </div>
        {onExport && (
          <Button variant="outline" size="sm" onClick={onExport}>
            <Download /> Exporter Excel
          </Button>
        )}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

const fmt = (n) => formatNumber(n)

// Carte d'erreur FR quand un rapport échoue (réseau / serveur).
function ErrorCard({ title, message }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        <p className="text-sm text-destructive">{message || 'Rapport indisponible'}</p>
      </CardContent>
    </Card>
  )
}

// Carte « chargement » explicite (libellé FR + squelette).
function LoadingCard({ title }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">Chargement…</p>
        <Skeleton className="mt-2 h-24 w-full" />
      </CardContent>
    </Card>
  )
}

export function Component() {
  const [sales, setSales] = useState(null)
  const [stock, setStock] = useState(null)
  const [service, setService] = useState(null)
  const [recurring, setRecurring] = useState(null)
  const [audit, setAudit] = useState(null)
  const [jobCosting, setJobCosting] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [commissions, setCommissions] = useState(null)
  // État par carte : 'loading' | 'ok' | 'error'.
  const [status, setStatus] = useState({})
  // Période optionnelle (?from=&to=) appliquée à ventes/stock/service.
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const setCardStatus = useCallback((key, value) => {
    setStatus((s) => ({ ...s, [key]: value }))
  }, [])

  // Repasse les cartes period-aware en « chargement » lors d'un changement de
  // période (déclenché par l'utilisateur, hors effet → conforme aux règles).
  const resetPeriodCards = () => {
    setStatus((s) => {
      const next = { ...s }
      delete next.sales
      delete next.stock
      delete next.service
      return next
    })
  }
  const onFrom = (e) => { resetPeriodCards(); setFrom(e.target.value) }
  const onTo = (e) => { resetPeriodCards(); setTo(e.target.value) }
  const onClearPeriod = () => { resetPeriodCards(); setFrom(''); setTo('') }

  // Charge un rapport et trace son état (ok/error) à la résolution. L'état
  // « loading » est implicite : status[key] indéfini → carte « Chargement… »
  // (on ne met pas setState de façon synchrone dans l'effet).
  const load = useCallback((key, promise, setter) => (
    promise
      .then((r) => { setter(r.data); setCardStatus(key, 'ok') })
      .catch(() => { setter(null); setCardStatus(key, 'error') })
  ), [setCardStatus])

  // Les rapports period-aware (ventes/stock/service) se rechargent au filtre.
  useEffect(() => {
    const params = {}
    if (from) params.from = from
    if (to) params.to = to
    load('sales', api.get('/reporting/reports/sales/', { params }), setSales)
    load('stock', api.get('/reporting/reports/stock/', { params }), setStock)
    load('service', api.get('/reporting/reports/service/', { params }), setService)
  }, [from, to, load])

  // Les insights (all-time) ne sont chargés qu'une fois.
  useEffect(() => {
    load('recurring', reportingApi.recurringRevenue(), setRecurring)
    load('audit', reportingApi.auditLog(), setAudit)
    // Réservé owner/responsable — un refus (403) est traité comme « erreur ».
    load('jobCosting', reportingApi.jobCosting(), setJobCosting)
    load('analytics', reportingApi.analytics(), setAnalytics)
    // N99 — réservé admin.
    load('commissions', reportingApi.commissions(), setCommissions)
  }, [load])

  const exportInsight = (slug) => () => reportingApi.insightXlsx(slug)
    .then(r => downloadXlsx(r.data, `${slug}.xlsx`)).catch(() => {})

  const periodParams = {}
  if (from) periodParams.from = from
  if (to) periodParams.to = to

  // Rendu d'une carte period-aware selon son état de chargement.
  const renderReportCard = (key, title, render) => {
    if (status[key] === 'loading' || status[key] === undefined) {
      return <LoadingCard title={title} />
    }
    if (status[key] === 'error') {
      return <ErrorCard title={title} message="Rapport indisponible" />
    }
    return render()
  }

  return (
    <div className="ui-root page" style={{ maxWidth: 1100 }}>
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h2>Rapports</h2>
      </div>

      <Tabs defaultValue="ventes">
        <TabsList className="flex-wrap">
          <TabsTrigger value="ventes">Ventes &amp; pipeline</TabsTrigger>
          <TabsTrigger value="stock">Stock</TabsTrigger>
          <TabsTrigger value="service">Service</TabsTrigger>
          <TabsTrigger value="insights">Insights</TabsTrigger>
        </TabsList>

        {/* ── Filtre de période (ventes / stock / service) ── */}
        <div className="my-3 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Du</span>
            <Input type="date" value={from} onChange={onFrom} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Au</span>
            <Input type="date" value={to} onChange={onTo} />
          </label>
          {(from || to) && (
            <Button variant="outline" size="sm" onClick={onClearPeriod}>
              Effacer la période
            </Button>
          )}
        </div>

        {/* ── Ventes & pipeline ── */}
        <TabsContent value="ventes">
          {renderReportCard('sales', 'Ventes & pipeline', () => (
            <ReportCard title="Ventes & pipeline" kind="sales" params={periodParams}>
              <Table headers={['Étape', 'Leads']}
                     rows={sales.funnel.map(f => [f.label, fmt(f.count)])}
                     footer={['Total', fmt(sumBy(sales.funnel, 'count'))]} />
              {sales.devis_par_statut?.length > 0 && (
                <>
                  <Subhead>Devis par statut</Subhead>
                  <Table headers={['Statut', 'Nombre']}
                         rows={sales.devis_par_statut.map(d => [d.label, fmt(d.count)])}
                         footer={['Total', fmt(sumBy(sales.devis_par_statut, 'count'))]} />
                </>
              )}
              <Subhead>Par responsable</Subhead>
              <Table headers={['Responsable', 'Leads', 'Gagnés']}
                     rows={sales.par_responsable.map(r => [r.owner__username || '—', fmt(r.count), fmt(r.gagnes)])}
                     footer={['Total', fmt(sumBy(sales.par_responsable, 'count')), fmt(sumBy(sales.par_responsable, 'gagnes'))]} />
              <Subhead>Pertes par motif</Subhead>
              <Table headers={['Motif', 'Nombre']}
                     rows={sales.perdus_par_motif.map(r => [r.motif_perte || 'Non précisé', fmt(r.count)])}
                     footer={['Total', fmt(sumBy(sales.perdus_par_motif, 'count'))]} />
            </ReportCard>
          ))}
        </TabsContent>

        {/* ── Stock ── */}
        <TabsContent value="stock">
          {renderReportCard('stock', 'Stock', () => (
            <ReportCard title="Stock" kind="stock" params={periodParams}>
              <p className="text-sm">
                Valorisation (vente) : <strong className="tabular-nums">{fmt(stock.valorisation_vente)} DH</strong>
                {' · '}achat (interne) : <span className="tabular-nums">{fmt(stock.valorisation_achat)} DH</span>
              </p>
              <Subhead>Par catégorie</Subhead>
              <Table headers={['Catégorie', 'Articles', 'Valeur vente HT']}
                     rows={stock.par_categorie.map(c => [c.categorie__nom || '—', fmt(c.nb), fmt(c.valeur_vente)])}
                     footer={['Total', fmt(sumBy(stock.par_categorie, 'nb')), fmt(sumBy(stock.par_categorie, 'valeur_vente'))]} />
              <Subhead>Stock bas</Subhead>
              <Table headers={['Produit', 'SKU', 'Stock', 'Seuil']}
                     rows={stock.bas_stock.map(p => [p.nom, p.sku || '—', fmt(p.quantite_stock), fmt(p.seuil_alerte)])} />
            </ReportCard>
          ))}
        </TabsContent>

        {/* ── Service ── */}
        <TabsContent value="service">
          {renderReportCard('service', 'Service (chantiers + SAV)', () => (
            <ReportCard title="Service (chantiers + SAV)" kind="service" params={periodParams}>
              <p className="text-sm">
                Tickets ouverts : <strong className="tabular-nums">{fmt(service.tickets_ouverts)}</strong>
                {' · '}résolus : <span className="tabular-nums">{fmt(service.tickets_resolus)}</span>
                {' · '}garanties expirant ≤90 j : <span className="tabular-nums">{fmt(service.garanties_expirantes_90j)}</span>
              </p>
              <Subhead>Chantiers par statut</Subhead>
              <Table headers={['Statut', 'Nombre']}
                     rows={service.chantiers_par_statut.map(c => [c.statut, fmt(c.count)])}
                     footer={['Total', fmt(sumBy(service.chantiers_par_statut, 'count'))]} />
              <Subhead>Activité technicien</Subhead>
              <Table headers={['Technicien', 'Interventions']}
                     rows={service.interventions_par_technicien.map(t => [t.technicien__username || '—', fmt(t.count)])}
                     footer={['Total', fmt(sumBy(service.interventions_par_technicien, 'count'))]} />
            </ReportCard>
          ))}
        </TabsContent>

        {/* ── Insights ── */}
        <TabsContent value="insights">
          <div className="space-y-6">
            <InsightCard title="Revenu récurrent (contrats de maintenance)"
                         onExport={exportInsight('recurring-revenue')}>
              {status.recurring === 'error' ? (
                <p className="text-sm text-destructive">Rapport indisponible</p>
              ) : recurring ? (
                <>
                  <p className="text-sm">
                    Mensuel équivalent : <strong className="tabular-nums">{fmt(recurring.monthly_total)} DH</strong>
                    {' · '}annuel équivalent : <strong className="tabular-nums">{fmt(recurring.annual_total)} DH</strong>
                    {' · '}contrats actifs : <span className="tabular-nums">{fmt(recurring.active_count)}</span>
                    {' · '}inactifs : <span className="tabular-nums">{fmt(recurring.lapsed_count)}</span>
                  </p>
                  <Subhead>Renouvellements / visites sous 90 jours</Subhead>
                  <Table headers={['Client', 'Périodicité', 'Prochaine visite', 'Mensuel équiv. (DH)']}
                         rows={recurring.upcoming.map(c => [c.client, c.periodicite_label, c.prochaine_visite || '—', fmt(c.monthly_equivalent)])}
                         footer={[`Total (${recurring.upcoming.length})`, '', '', fmt(sumBy(recurring.upcoming, 'monthly_equivalent'))]} />
                </>
              ) : <p className="text-sm text-muted-foreground">Chargement…</p>}
            </InsightCard>

            <InsightCard title="Journal d'activité (qui a fait quoi)"
                         onExport={exportInsight('audit-log')}>
              {status.audit === 'error' ? (
                <p className="text-sm text-destructive">Rapport indisponible</p>
              ) : audit ? (
                <Table headers={['Date', 'Utilisateur', 'Type', 'Référence', 'Action']}
                       rows={audit.items.map(it => [
                         (it.date || '').replace('T', ' ').slice(0, 16),
                         it.user || '—', it.type_label, it.object_ref, it.summary,
                       ])} />
              ) : <p className="text-sm text-muted-foreground">Chargement…</p>}
            </InsightCard>

            <InsightCard title="Coût de revient par chantier"
                         note="(interne — visible owner/responsable)"
                         onExport={jobCosting ? exportInsight('job-costing') : undefined}>
              {status.jobCosting === 'error' ? (
                <p className="text-sm text-muted-foreground">Réservé admin / responsable.</p>
              ) : jobCosting ? (
                <>
                  <p className="text-sm">
                    Facturé HT : <strong className="tabular-nums">{fmt(jobCosting.total_invoiced_ht)} DH</strong>
                    {' · '}coût estimé : <span className="tabular-nums">{fmt(jobCosting.total_cost_estimate)} DH</span>
                    {' · '}marge : <strong className="tabular-nums">{fmt(jobCosting.total_margin)} DH</strong>
                  </p>
                  <Table headers={['Chantier', 'Client', 'Facturé HT', 'Coût estimé', 'Marge', 'Marge %']}
                         rows={jobCosting.chantiers.map(c => [
                           c.ref, c.client, fmt(c.invoiced_ht), fmt(c.cost_estimate),
                           fmt(c.margin), `${c.margin_pct} %`,
                         ])}
                         footer={[`Total (${jobCosting.chantiers.length})`, '',
                                  fmt(sumBy(jobCosting.chantiers, 'invoiced_ht')),
                                  fmt(sumBy(jobCosting.chantiers, 'cost_estimate')),
                                  fmt(sumBy(jobCosting.chantiers, 'margin')), '']} />
                </>
              ) : <p className="text-sm text-muted-foreground">Chargement…</p>}
            </InsightCard>

            <InsightCard title="Analytics (délais & kWc installés)"
                         onExport={exportInsight('analytics')}>
              {status.analytics === 'error' ? (
                <p className="text-sm text-destructive">Rapport indisponible</p>
              ) : analytics ? (
                <>
                  <p className="text-sm">
                    Délai moyen lead → signature : <strong className="tabular-nums">{analytics.avg_days_lead_to_signature ?? '—'} j</strong>
                    {' · '}signature → mise en service : <strong className="tabular-nums">{analytics.avg_days_signature_to_commissioning ?? '—'} j</strong>
                  </p>
                  <Subhead>kWc installés par mois</Subhead>
                  {analytics.kwc_by_month.length > 0 ? (
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={analytics.kwc_by_month.map(m => ({ mois: m.mois, kwc: Number(m.kwc) }))}>
                        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                        <XAxis dataKey="mois" tick={{ fontSize: 11, fill: CHART_AXIS }} stroke={CHART_GRID} />
                        <YAxis tick={{ fontSize: 11, fill: CHART_AXIS }} stroke={CHART_GRID} />
                        <Tooltip
                          contentStyle={{
                            borderRadius: 8, fontSize: 12,
                            background: 'var(--color-popover)',
                            border: '1px solid var(--color-border)',
                            color: 'var(--color-popover-foreground)',
                          }}
                        />
                        <Bar dataKey="kwc" name="kWc" fill={CHART_PRIMARY} radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyState icon={BarChart3} title="Aucune donnée" className="border-0 py-6" />
                  )}
                </>
              ) : <p className="text-sm text-muted-foreground">Chargement…</p>}
            </InsightCard>

            <InsightCard title="Commissions commerciales"
                         note="(interne — visible admin ; configuré dans Paramètres)"
                         onExport={commissions?.enabled
                           ? exportInsight('commissions') : undefined}>
              {status.commissions === 'error' && (
                <p className="text-sm text-muted-foreground">Réservé admin.</p>
              )}
              {commissions && !commissions.enabled && (
                <p className="text-sm text-muted-foreground">
                  Commissions désactivées. Activez-les dans Paramètres → Devis &amp;
                  Factures → Commission commerciale.
                </p>
              )}
              {commissions && commissions.enabled && (
                <>
                  <p className="text-sm">
                    Total commissions : <strong className="tabular-nums">{fmt(commissions.total)} DH</strong>
                  </p>
                  <Table headers={['Commercial', 'Devis signés',
                                   commissions.base_label, 'Commission (DH)']}
                         rows={commissions.rows.map(r => [
                           r.commercial, fmt(r.count), fmt(r.base), fmt(r.commission),
                         ])}
                         footer={['Total', fmt(sumBy(commissions.rows, 'count')),
                                  fmt(sumBy(commissions.rows, 'base')),
                                  fmt(sumBy(commissions.rows, 'commission'))]} />
                </>
              )}
            </InsightCard>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
