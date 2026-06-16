// T13/T14/T15 — Hub « Rapports » : ventes/pipeline, stock, service (chantier +
// SAV). Lecture seule ; chaque rapport est exportable en .xlsx. Données
// agrégées côté serveur, bornées à la société.
import { useEffect, useState } from 'react'
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

export function Component() {
  const [sales, setSales] = useState(null)
  const [stock, setStock] = useState(null)
  const [service, setService] = useState(null)

  useEffect(() => {
    reportingApi.salesReport().then(r => setSales(r.data)).catch(() => {})
    reportingApi.stockReport().then(r => setStock(r.data)).catch(() => {})
    reportingApi.serviceReport().then(r => setService(r.data)).catch(() => {})
  }, [])

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
    </div>
  )
}
