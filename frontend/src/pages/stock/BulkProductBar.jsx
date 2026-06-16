// T8 — barre d'actions EN MASSE du catalogue produit. Visible dès qu'un produit
// est coché. Prix (% ou fixe), garantie, catégorie, marque, export Excel. La
// règle (prix d'achat jamais touché) est appliquée SERVEUR ; ici, UI seulement.
import { useState } from 'react'

export default function BulkProductBar({
  count, categories = [], marques = [], busy, onAction, onExport, onClear,
}) {
  const [panel, setPanel] = useState(null)
  const [priceMode, setPriceMode] = useState('percent')
  const [priceVal, setPriceVal] = useState('')
  const [gar, setGar] = useState('')
  const [garProd, setGarProd] = useState('')
  const [cat, setCat] = useState('')
  const [marque, setMarque] = useState('')

  const toggle = (n) => setPanel((p) => (p === n ? null : n))
  const run = (action, params) => { onAction(action, params); setPanel(null) }

  return (
    <div className="bulk-bar" role="region" aria-label="Actions produits en masse"
         style={{ background: '#0f172a', color: '#fff', borderRadius: 10, padding: '10px 14px', marginBottom: 12, display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
      <div><strong>{count}</strong> produit{count > 1 ? 's' : ''} sélectionné{count > 1 ? 's' : ''}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
        <button type="button" className="btn btn-sm btn-outline" disabled={busy}
                onClick={() => toggle('price')}>Prix</button>
        <button type="button" className="btn btn-sm btn-outline" disabled={busy}
                onClick={() => toggle('warranty')}>Garantie</button>
        <button type="button" className="btn btn-sm btn-outline" disabled={busy}
                onClick={() => toggle('cat')}>Catégorie</button>
        <button type="button" className="btn btn-sm btn-outline" disabled={busy}
                onClick={() => toggle('brand')}>Marque</button>
        <button type="button" className="btn btn-sm btn-outline" disabled={busy}
                onClick={onExport}>⬇ Exporter Excel</button>
        <button type="button" className="btn btn-sm" disabled={busy} onClick={onClear}
                style={{ color: '#cbd5e1' }}>✕ Désélectionner</button>
      </div>

      {panel === 'price' && (
        <div style={{ flexBasis: '100%', display: 'flex', gap: 8, alignItems: 'center', paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.15)' }}>
          <select className="form-control" style={{ maxWidth: 160, color: '#0f172a' }}
                  value={priceMode} onChange={(e) => setPriceMode(e.target.value)}>
            <option value="percent">Variation (%)</option>
            <option value="fixed">Prix fixe (HT)</option>
          </select>
          <input className="form-control" type="number" step="any" style={{ maxWidth: 140, color: '#0f172a' }}
                 placeholder={priceMode === 'percent' ? 'ex. 10 ou -5' : 'ex. 1200'}
                 value={priceVal} onChange={(e) => setPriceVal(e.target.value)} />
          <button type="button" className="btn btn-sm btn-primary" disabled={priceVal === ''}
                  onClick={() => run('set_price', { mode: priceMode, valeur: priceVal })}>Appliquer</button>
          <span style={{ fontSize: 12, color: '#cbd5e1' }}>Le prix d'achat n'est jamais modifié.</span>
        </div>
      )}
      {panel === 'warranty' && (
        <div style={{ flexBasis: '100%', display: 'flex', gap: 8, alignItems: 'center', paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.15)' }}>
          <input className="form-control" type="number" min="0" style={{ maxWidth: 160, color: '#0f172a' }}
                 placeholder="Garantie (mois)" value={gar} onChange={(e) => setGar(e.target.value)} />
          <input className="form-control" type="number" min="0" style={{ maxWidth: 200, color: '#0f172a' }}
                 placeholder="Garantie production (mois)" value={garProd} onChange={(e) => setGarProd(e.target.value)} />
          <button type="button" className="btn btn-sm btn-primary" disabled={gar === '' && garProd === ''}
                  onClick={() => run('set_warranty', { garantie_mois: gar, garantie_production_mois: garProd })}>Appliquer</button>
        </div>
      )}
      {panel === 'cat' && (
        <div style={{ flexBasis: '100%', display: 'flex', gap: 8, alignItems: 'center', paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.15)' }}>
          <select className="form-control" style={{ maxWidth: 240, color: '#0f172a' }}
                  value={cat} onChange={(e) => setCat(e.target.value)}>
            <option value="">— Aucune catégorie —</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
          </select>
          <button type="button" className="btn btn-sm btn-primary"
                  onClick={() => run('set_category', { categorie_id: cat || null })}>Appliquer</button>
        </div>
      )}
      {panel === 'brand' && (
        <div style={{ flexBasis: '100%', display: 'flex', gap: 8, alignItems: 'center', paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.15)' }}>
          <input className="form-control" list="bpb-marques" style={{ maxWidth: 240, color: '#0f172a' }}
                 placeholder="Marque" value={marque} onChange={(e) => setMarque(e.target.value)} />
          <datalist id="bpb-marques">
            {marques.map((m) => <option key={m.id} value={m.nom} />)}
          </datalist>
          <button type="button" className="btn btn-sm btn-primary"
                  onClick={() => run('set_brand', { marque })}>Appliquer</button>
        </div>
      )}
    </div>
  )
}
