import { useEffect, useState } from 'react'
import reportingApi from '../../api/reportingApi'
import PeriodFilter from './PeriodFilter'
import { downloadBlob } from '../../utils/downloadBlob'

const dh = (v) => `${Number(v ?? 0).toLocaleString('fr-MA', { maximumFractionDigits: 0 })} MAD`

export default function StockReportPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [params, setParams] = useState({})

  useEffect(() => {
    let alive = true
    const run = async () => {
      await Promise.resolve()
      if (!alive) return
      setLoading(true)
      try {
        const r = await reportingApi.getStock(params)
        if (alive) setData(r.data)
      } catch { /* ignore */ }
      if (alive) setLoading(false)
    }
    run()
    return () => { alive = false }
  }, [params])

  const exportXlsx = async () => {
    try {
      const r = await reportingApi.getStockXlsx(params)
      downloadBlob(r.data, 'rapport_stock.xlsx')
    } catch { alert('Export indisponible.') }
  }

  return (
    <div className="page" style={{ maxWidth: 1150 }}>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <h2>Rapport stock (interne)</h2>
        <button className="btn btn-sm" onClick={exportXlsx}>Exporter (.xlsx)</button>
      </div>
      <PeriodFilter onApply={setParams} />

      {loading || !data ? <p className="page-loading">Chargement…</p> : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            <Kpi label="Valeur de vente du stock" value={dh(data.valorisation_totale.valeur_vente)} color="#3b82f6" />
            <Kpi label="Valeur d'achat (interne)" value={dh(data.valorisation_totale.valeur_achat)} color="#f59e0b"
              sub="Usage interne uniquement" />
            <Kpi label="Marge potentielle" value={dh(data.valorisation_totale.marge_potentielle)} color="#22c55e" />
          </div>

          <p style={{ fontSize: 12, color: '#b45309', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '0.5rem 0.75rem', marginBottom: '1.25rem' }}>
            Ce rapport est interne : la valeur et le prix d'achat ne doivent jamais être communiqués au client.
          </p>

          <Card title="Valorisation par produit">
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Produit</th><th>Catégorie</th><th>Marque</th>
                    <th className="ta-right">Qté</th>
                    <th className="ta-right">P. achat</th><th className="ta-right">P. vente</th>
                    <th className="ta-right">Val. achat</th><th className="ta-right">Val. vente</th>
                    <th className="ta-right">Marge</th>
                  </tr>
                </thead>
                <tbody>
                  {data.valorisation.map((r, i) => (
                    <tr key={i}>
                      <td><strong>{r.nom}</strong></td>
                      <td>{r.categorie}</td><td>{r.marque}</td>
                      <td className="ta-right">{r.quantite}</td>
                      <td className="ta-right">{dh(r.prix_achat)}</td>
                      <td className="ta-right">{dh(r.prix_vente)}</td>
                      <td className="ta-right">{dh(r.valeur_achat)}</td>
                      <td className="ta-right">{dh(r.valeur_vente)}</td>
                      <td className="ta-right">{dh(r.marge_potentielle)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title={`Produits sous seuil d'alerte (${data.sous_seuil.length})`}>
            <table className="data-table">
              <thead><tr><th>Produit</th><th>SKU</th><th className="ta-right">Stock</th><th className="ta-right">Seuil</th></tr></thead>
              <tbody>
                {data.sous_seuil.length === 0 ? (
                  <tr><td colSpan={4} style={empty}>Tous les stocks sont au-dessus du seuil.</td></tr>
                ) : data.sous_seuil.map((r, i) => (
                  <tr key={i}>
                    <td>{r.nom}</td><td>{r.sku}</td>
                    <td className="ta-right" style={{ color: r.quantite_stock <= 0 ? '#dc2626' : '#d97706', fontWeight: 600 }}>{r.quantite_stock}</td>
                    <td className="ta-right">{r.seuil_alerte}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
            <Card title="Par catégorie">
              <CatTable rows={data.par_categorie} keyName="categorie" />
            </Card>
            <Card title="Par marque">
              <CatTable rows={data.par_marque} keyName="marque" />
            </Card>
          </div>

          <Card title={`Historique des mouvements (${data.mouvements.length})`}>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead><tr><th>Date</th><th>Produit</th><th>Type</th><th className="ta-right">Qté</th><th className="ta-right">Avant</th><th className="ta-right">Après</th><th>Réf.</th></tr></thead>
                <tbody>
                  {data.mouvements.length === 0 ? (
                    <tr><td colSpan={7} style={empty}>Aucun mouvement sur la période.</td></tr>
                  ) : data.mouvements.map((m, i) => (
                    <tr key={i}>
                      <td>{m.date}</td><td>{m.produit}</td><td>{m.type}</td>
                      <td className="ta-right">{m.quantite}</td>
                      <td className="ta-right">{m.quantite_avant}</td>
                      <td className="ta-right">{m.quantite_apres}</td>
                      <td>{m.reference}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}

function CatTable({ rows, keyName }) {
  return (
    <table className="data-table">
      <thead><tr><th>{keyName === 'categorie' ? 'Catégorie' : 'Marque'}</th><th className="ta-right">Nb</th><th className="ta-right">Val. achat</th><th className="ta-right">Val. vente</th></tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td>{r[keyName]}</td><td className="ta-right">{r.nb}</td>
            <td className="ta-right">{dh(r.valeur_achat)}</td>
            <td className="ta-right">{dh(r.valeur_vente)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Kpi({ label, value, color, sub }) {
  return (
    <div style={{ background: '#fff', borderRadius: 14, padding: '1.1rem 1.3rem', boxShadow: '0 1px 4px rgba(0,0,0,0.07)' }}>
      <div style={{ fontSize: 12.5, color: '#64748b', fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function Card({ title, children }) {
  return (
    <div style={{ background: '#fff', borderRadius: 14, padding: '1.1rem 1.3rem', boxShadow: '0 1px 4px rgba(0,0,0,0.07)', marginBottom: '1.25rem' }}>
      <h3 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#1e293b', margin: '0 0 0.75rem' }}>{title}</h3>
      {children}
    </div>
  )
}

const empty = { textAlign: 'center', color: '#94a3b8', padding: '1.5rem' }
