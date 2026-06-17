// T13/T14/T15 — Hub « Rapports » : ventes/pipeline, stock, service (chantier +
// SAV). Lecture seule ; chaque rapport est exportable en .xlsx. Données
// agrégées côté serveur, bornées à la société.
import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import reportingApi from '../api/reportingApi'
import { downloadXlsx } from '../api/importApi'

function Table({ headers, rows }) {
  return (
    <table className="data-table" style={{ marginBottom: 8 }}>
      <thead><tr>{headers.map(h => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>
        ))}
        {!rows.length && <tr><td colSpan={headers.length} style={{ color: '#94a3b8' }}>Aucune donnée.</td></tr>}
      </tbody>
    </table>
  )
}

function Card({ title, kind, children }) {
  const onExport = () => reportingApi.reportXlsx(kind)
    .then(r => downloadXlsx(r.data, `rapport-${kind}.xlsx`)).catch(() => {})
  return (
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: '1.25rem 1.4rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        <button className="btn btn-sm btn-outline" onClick={onExport}>⬇ Exporter Excel</button>
      </div>
      {children}
    </div>
  )
}

// Carte « insight » avec un bouton d'export personnalisé (chemin différent des
// rapports T13/T14/T15). onExport optionnel : pas de bouton si absent.
function InsightCard({ title, note, onExport, children }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: '1.25rem 1.4rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h3 style={{ margin: 0 }}>{title}</h3>
          {note && <p style={{ margin: '2px 0 0', fontSize: 12, color: '#94a3b8' }}>{note}</p>}
        </div>
        {onExport && <button className="btn btn-sm btn-outline" onClick={onExport}>⬇ Exporter Excel</button>}
      </div>
      {children}
    </div>
  )
}

const fmt = (n) => Number(n || 0).toLocaleString('fr-MA')

export function Component() {
  const [sales, setSales] = useState(null)
  const [stock, setStock] = useState(null)
  const [service, setService] = useState(null)
  const [recurring, setRecurring] = useState(null)
  const [audit, setAudit] = useState(null)
  const [jobCosting, setJobCosting] = useState(null)
  const [analytics, setAnalytics] = useState(null)

  useEffect(() => {
    reportingApi.salesReport().then(r => setSales(r.data)).catch(() => {})
    reportingApi.stockReport().then(r => setStock(r.data)).catch(() => {})
    reportingApi.serviceReport().then(r => setService(r.data)).catch(() => {})
    reportingApi.recurringRevenue().then(r => setRecurring(r.data)).catch(() => {})
    reportingApi.auditLog().then(r => setAudit(r.data)).catch(() => {})
    // Réservé owner/responsable — un refus (403) laisse simplement la carte vide.
    reportingApi.jobCosting().then(r => setJobCosting(r.data)).catch(() => {})
    reportingApi.analytics().then(r => setAnalytics(r.data)).catch(() => {})
  }, [])

  const exportInsight = (slug) => () => reportingApi.insightXlsx(slug)
    .then(r => downloadXlsx(r.data, `${slug}.xlsx`)).catch(() => {})

  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      <div className="page-header"><h2>Rapports</h2></div>

      <Card title="Ventes & pipeline" kind="sales">
        {sales && (
          <>
            <Table headers={['Étape', 'Leads']}
                   rows={sales.funnel.map(f => [f.label, f.count])} />
            <h4 style={{ margin: '12px 0 4px', fontSize: 13 }}>Par responsable</h4>
            <Table headers={['Responsable', 'Leads', 'Gagnés']}
                   rows={sales.par_responsable.map(r => [r.owner__username || '—', r.count, r.gagnes])} />
            <h4 style={{ margin: '12px 0 4px', fontSize: 13 }}>Pertes par motif</h4>
            <Table headers={['Motif', 'Nombre']}
                   rows={sales.perdus_par_motif.map(r => [r.motif_perte || 'Non précisé', r.count])} />
          </>
        )}
      </Card>

      <Card title="Stock" kind="stock">
        {stock && (
          <>
            <p style={{ fontSize: 13 }}>
              Valorisation (vente) : <strong>{Number(stock.valorisation_vente).toLocaleString('fr-MA')} DH</strong>
              {' · '}achat (interne) : {Number(stock.valorisation_achat).toLocaleString('fr-MA')} DH
            </p>
            <h4 style={{ margin: '12px 0 4px', fontSize: 13 }}>Par catégorie</h4>
            <Table headers={['Catégorie', 'Articles', 'Valeur vente HT']}
                   rows={stock.par_categorie.map(c => [c.categorie__nom || '—', c.nb, Number(c.valeur_vente).toLocaleString('fr-MA')])} />
            <h4 style={{ margin: '12px 0 4px', fontSize: 13 }}>Stock bas</h4>
            <Table headers={['Produit', 'SKU', 'Stock', 'Seuil']}
                   rows={stock.bas_stock.map(p => [p.nom, p.sku || '—', p.quantite_stock, p.seuil_alerte])} />
          </>
        )}
      </Card>

      <Card title="Service (chantiers + SAV)" kind="service">
        {service && (
          <>
            <p style={{ fontSize: 13 }}>
              Tickets ouverts : <strong>{service.tickets_ouverts}</strong> ·
              {' '}résolus : {service.tickets_resolus} ·
              {' '}garanties expirant ≤90 j : {service.garanties_expirantes_90j}
            </p>
            <h4 style={{ margin: '12px 0 4px', fontSize: 13 }}>Chantiers par statut</h4>
            <Table headers={['Statut', 'Nombre']}
                   rows={service.chantiers_par_statut.map(c => [c.statut, c.count])} />
            <h4 style={{ margin: '12px 0 4px', fontSize: 13 }}>Activité technicien</h4>
            <Table headers={['Technicien', 'Interventions']}
                   rows={service.interventions_par_technicien.map(t => [t.technicien__username || '—', t.count])} />
          </>
        )}
      </Card>

      <InsightCard title="Revenu récurrent (contrats de maintenance)"
                   onExport={exportInsight('recurring-revenue')}>
        {recurring && (
          <>
            <p style={{ fontSize: 13 }}>
              Mensuel équivalent : <strong>{fmt(recurring.monthly_total)} DH</strong>
              {' · '}annuel équivalent : <strong>{fmt(recurring.annual_total)} DH</strong>
              {' · '}contrats actifs : {recurring.active_count}
              {' · '}inactifs : {recurring.lapsed_count}
            </p>
            <h4 style={{ margin: '12px 0 4px', fontSize: 13 }}>Renouvellements / visites sous 90 jours</h4>
            <Table headers={['Client', 'Périodicité', 'Prochaine visite', 'Mensuel équiv. (DH)']}
                   rows={recurring.upcoming.map(c => [c.client, c.periodicite_label, c.prochaine_visite || '—', fmt(c.monthly_equivalent)])} />
          </>
        )}
      </InsightCard>

      <InsightCard title="Journal d'activité (qui a fait quoi)"
                   onExport={exportInsight('audit-log')}>
        {audit && (
          <Table headers={['Date', 'Utilisateur', 'Type', 'Référence', 'Action']}
                 rows={audit.items.map(it => [
                   (it.date || '').replace('T', ' ').slice(0, 16),
                   it.user || '—', it.type_label, it.object_ref, it.summary,
                 ])} />
        )}
      </InsightCard>

      <InsightCard title="Coût de revient par chantier"
                   note="(interne — visible owner/responsable)">
        {jobCosting && (
          <>
            <p style={{ fontSize: 13 }}>
              Facturé HT : <strong>{fmt(jobCosting.total_invoiced_ht)} DH</strong>
              {' · '}coût estimé : {fmt(jobCosting.total_cost_estimate)} DH
              {' · '}marge : <strong>{fmt(jobCosting.total_margin)} DH</strong>
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
        {analytics && (
          <>
            <p style={{ fontSize: 13 }}>
              Délai moyen lead → signature : <strong>{analytics.avg_days_lead_to_signature ?? '—'} j</strong>
              {' · '}signature → mise en service : <strong>{analytics.avg_days_signature_to_commissioning ?? '—'} j</strong>
            </p>
            <h4 style={{ margin: '12px 0 4px', fontSize: 13 }}>kWc installés par mois</h4>
            {analytics.kwc_by_month.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={analytics.kwc_by_month.map(m => ({ mois: m.mois, kwc: Number(m.kwc) }))}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="mois" fontSize={11} />
                  <YAxis fontSize={11} />
                  <Tooltip />
                  <Bar dataKey="kwc" name="kWc" fill="#2563eb" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p style={{ color: '#94a3b8', fontSize: 13 }}>Aucune donnée.</p>
            )}
          </>
        )}
      </InsightCard>
    </div>
  )
}
