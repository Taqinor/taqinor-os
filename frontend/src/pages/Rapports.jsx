// T13/T14/T15 — Hub « Rapports » : ventes/pipeline, stock, service (chantier +
// SAV). Lecture seule ; chaque rapport est exportable en .xlsx. Données
// agrégées côté serveur, bornées à la société.
import { useEffect, useState } from 'react'
import { Download, BarChart3 } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import reportingApi from '../api/reportingApi'
import { downloadXlsx } from '../api/importApi'
import { formatNumber } from '../lib/format'
import {
  Button, Card, CardHeader, CardTitle, CardDescription, CardContent,
  Tabs, TabsList, TabsTrigger, TabsContent, Skeleton, EmptyState,
} from '../ui'

const CHART_PRIMARY = 'var(--color-info)'
const CHART_GRID = 'var(--color-border)'
const CHART_AXIS = 'var(--color-muted-foreground)'

// Tableau de données restylé (conserve la classe sémantique .data-table).
function Table({ headers, rows }) {
  return (
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
    </table>
  )
}

// Sous-titre interne d'une carte.
function Subhead({ children }) {
  return (
    <h4 className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </h4>
  )
}

// Carte de rapport T13/T14/T15 (export Excel via le chemin /reports/<kind>/).
function ReportCard({ title, kind, children }) {
  const onExport = () => reportingApi.reportXlsx(kind)
    .then(r => downloadXlsx(r.data, `rapport-${kind}.xlsx`)).catch(() => {})
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

// Squelette de carte pendant le chargement.
function CardSkeleton() {
  return (
    <Card>
      <CardHeader><Skeleton className="h-4 w-1/3" /></CardHeader>
      <CardContent className="space-y-2">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-24 w-full" />
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

  useEffect(() => {
    reportingApi.salesReport().then(r => setSales(r.data)).catch(() => {})
    reportingApi.stockReport().then(r => setStock(r.data)).catch(() => {})
    reportingApi.serviceReport().then(r => setService(r.data)).catch(() => {})
    reportingApi.recurringRevenue().then(r => setRecurring(r.data)).catch(() => {})
    reportingApi.auditLog().then(r => setAudit(r.data)).catch(() => {})
    // Réservé owner/responsable — un refus (403) laisse simplement la carte vide.
    reportingApi.jobCosting().then(r => setJobCosting(r.data)).catch(() => {})
    reportingApi.analytics().then(r => setAnalytics(r.data)).catch(() => {})
    // N99 — réservé admin ; un refus (403) laisse la carte vide.
    reportingApi.commissions().then(r => setCommissions(r.data)).catch(() => {})
  }, [])

  const exportInsight = (slug) => () => reportingApi.insightXlsx(slug)
    .then(r => downloadXlsx(r.data, `${slug}.xlsx`)).catch(() => {})

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

        {/* ── Ventes & pipeline ── */}
        <TabsContent value="ventes">
          {sales ? (
            <ReportCard title="Ventes & pipeline" kind="sales">
              <Table headers={['Étape', 'Leads']}
                     rows={sales.funnel.map(f => [f.label, fmt(f.count)])} />
              <Subhead>Par responsable</Subhead>
              <Table headers={['Responsable', 'Leads', 'Gagnés']}
                     rows={sales.par_responsable.map(r => [r.owner__username || '—', fmt(r.count), fmt(r.gagnes)])} />
              <Subhead>Pertes par motif</Subhead>
              <Table headers={['Motif', 'Nombre']}
                     rows={sales.perdus_par_motif.map(r => [r.motif_perte || 'Non précisé', fmt(r.count)])} />
            </ReportCard>
          ) : <CardSkeleton />}
        </TabsContent>

        {/* ── Stock ── */}
        <TabsContent value="stock">
          {stock ? (
            <ReportCard title="Stock" kind="stock">
              <p className="text-sm">
                Valorisation (vente) : <strong className="tabular-nums">{fmt(stock.valorisation_vente)} DH</strong>
                {' · '}achat (interne) : <span className="tabular-nums">{fmt(stock.valorisation_achat)} DH</span>
              </p>
              <Subhead>Par catégorie</Subhead>
              <Table headers={['Catégorie', 'Articles', 'Valeur vente HT']}
                     rows={stock.par_categorie.map(c => [c.categorie__nom || '—', fmt(c.nb), fmt(c.valeur_vente)])} />
              <Subhead>Stock bas</Subhead>
              <Table headers={['Produit', 'SKU', 'Stock', 'Seuil']}
                     rows={stock.bas_stock.map(p => [p.nom, p.sku || '—', fmt(p.quantite_stock), fmt(p.seuil_alerte)])} />
            </ReportCard>
          ) : <CardSkeleton />}
        </TabsContent>

        {/* ── Service ── */}
        <TabsContent value="service">
          {service ? (
            <ReportCard title="Service (chantiers + SAV)" kind="service">
              <p className="text-sm">
                Tickets ouverts : <strong className="tabular-nums">{fmt(service.tickets_ouverts)}</strong>
                {' · '}résolus : <span className="tabular-nums">{fmt(service.tickets_resolus)}</span>
                {' · '}garanties expirant ≤90 j : <span className="tabular-nums">{fmt(service.garanties_expirantes_90j)}</span>
              </p>
              <Subhead>Chantiers par statut</Subhead>
              <Table headers={['Statut', 'Nombre']}
                     rows={service.chantiers_par_statut.map(c => [c.statut, fmt(c.count)])} />
              <Subhead>Activité technicien</Subhead>
              <Table headers={['Technicien', 'Interventions']}
                     rows={service.interventions_par_technicien.map(t => [t.technicien__username || '—', fmt(t.count)])} />
            </ReportCard>
          ) : <CardSkeleton />}
        </TabsContent>

        {/* ── Insights ── */}
        <TabsContent value="insights">
          <div className="space-y-6">
            <InsightCard title="Revenu récurrent (contrats de maintenance)"
                         onExport={exportInsight('recurring-revenue')}>
              {recurring ? (
                <>
                  <p className="text-sm">
                    Mensuel équivalent : <strong className="tabular-nums">{fmt(recurring.monthly_total)} DH</strong>
                    {' · '}annuel équivalent : <strong className="tabular-nums">{fmt(recurring.annual_total)} DH</strong>
                    {' · '}contrats actifs : <span className="tabular-nums">{fmt(recurring.active_count)}</span>
                    {' · '}inactifs : <span className="tabular-nums">{fmt(recurring.lapsed_count)}</span>
                  </p>
                  <Subhead>Renouvellements / visites sous 90 jours</Subhead>
                  <Table headers={['Client', 'Périodicité', 'Prochaine visite', 'Mensuel équiv. (DH)']}
                         rows={recurring.upcoming.map(c => [c.client, c.periodicite_label, c.prochaine_visite || '—', fmt(c.monthly_equivalent)])} />
                </>
              ) : <Skeleton className="h-20 w-full" />}
            </InsightCard>

            <InsightCard title="Journal d'activité (qui a fait quoi)"
                         onExport={exportInsight('audit-log')}>
              {audit ? (
                <Table headers={['Date', 'Utilisateur', 'Type', 'Référence', 'Action']}
                       rows={audit.items.map(it => [
                         (it.date || '').replace('T', ' ').slice(0, 16),
                         it.user || '—', it.type_label, it.object_ref, it.summary,
                       ])} />
              ) : <Skeleton className="h-20 w-full" />}
            </InsightCard>

            <InsightCard title="Coût de revient par chantier"
                         note="(interne — visible owner/responsable)">
              {jobCosting && (
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
                         ])} />
                </>
              )}
            </InsightCard>

            <InsightCard title="Analytics (délais & kWc installés)"
                         onExport={exportInsight('analytics')}>
              {analytics ? (
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
              ) : <Skeleton className="h-20 w-full" />}
            </InsightCard>

            <InsightCard title="Commissions commerciales"
                         note="(interne — visible admin ; configuré dans Paramètres)"
                         onExport={commissions?.enabled
                           ? exportInsight('commissions') : undefined}>
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
                         ])} />
                </>
              )}
            </InsightCard>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
