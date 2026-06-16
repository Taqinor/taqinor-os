// N4 — Checklist d'exécution du chantier (étapes cochables, avancement %).
// N9 — Sur les étapes « capture de série », on peut saisir un produit + n° de
// série qui crée un équipement du parc. La saisie de série ne bloque JAMAIS
// la complétion (cocher reste possible sans série).
import { useEffect, useState } from 'react'
import installationsApi from '../../api/installationsApi'
import ProduitPicker from '../../components/ProduitPicker'

export default function ChantierChecklist({ installationId, produits, onChanged }) {
  const [items, setItems] = useState([])
  const [completion, setCompletion] = useState(null)
  const [loading, setLoading] = useState(true)
  // Saisies de série en attente, par clé d'étape : { produit, numero_serie }
  const [serie, setSerie] = useState({})

  const load = () => {
    installationsApi.getChecklist(installationId)
      .then((r) => { setItems(r.data.items ?? []); setCompletion(r.data.completion) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [installationId]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = async (item, fait) => {
    const payload = { cle: item.cle, fait }
    // Sur une étape de capture, joindre l'éventuelle série saisie (optionnel).
    if (fait && item.capture_serie) {
      const s = serie[item.cle]
      if (s?.produit) {
        payload.equipements = [{ produit: s.produit, numero_serie: s.numero_serie || '' }]
      }
    }
    try {
      const r = await installationsApi.cocherChecklist(installationId, payload)
      setItems(r.data.items ?? [])
      setCompletion(r.data.completion)
      setSerie((prev) => ({ ...prev, [item.cle]: undefined }))
      onChanged?.()
    } catch { /* erreur silencieuse */ }
  }

  const setSerieField = (cle, k, v) =>
    setSerie((prev) => ({ ...prev, [cle]: { ...(prev[cle] ?? {}), [k]: v } }))

  return (
    <div className="form-section">
      <div className="form-section-header">
        <span className="form-section-title">✅ Checklist d'exécution</span>
        {completion != null && (
          <span style={{ fontSize: 13, fontWeight: 700, color: completion === 100 ? '#16a34a' : '#475569' }}>
            {completion}%
          </span>
        )}
      </div>
      {completion != null && (
        <div style={{ height: 8, background: '#e2e8f0', borderRadius: 4, marginBottom: 10, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${completion}%`,
                        background: completion === 100 ? '#16a34a' : '#3b82f6' }} />
        </div>
      )}
      {loading ? (
        <p className="gen-hint">Chargement…</p>
      ) : items.length === 0 ? (
        <p className="gen-hint">Aucune étape (configurez-les dans Paramètres → Chantiers).</p>
      ) : (
        <div>
          {items.map((item) => (
            <div key={item.id} style={{ padding: '6px 0', borderBottom: '1px solid #f1f5f9' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={item.fait}
                       onChange={(e) => toggle(item, e.target.checked)} />
                <span style={{ textDecoration: item.fait ? 'line-through' : 'none',
                               color: item.fait ? '#94a3b8' : '#0f172a' }}>
                  {item.libelle}
                </span>
                {item.fait && item.fait_par_nom && (
                  <span className="gen-hint" style={{ marginLeft: 'auto', fontSize: 11 }}>
                    par {item.fait_par_nom}
                  </span>
                )}
              </label>
              {/* N9 — saisie optionnelle de série sur les étapes concernées. */}
              {item.capture_serie && !item.fait && (
                <div className="form-row" style={{ marginTop: 6, marginLeft: 24 }}>
                  <div className="form-group fg-grow">
                    <ProduitPicker produits={produits ?? []}
                                   value={serie[item.cle]?.produit ?? ''}
                                   onChange={(v) => setSerieField(item.cle, 'produit', v)} />
                  </div>
                  <div className="form-group">
                    <input className="form-control" placeholder="N° de série (optionnel)"
                           value={serie[item.cle]?.numero_serie ?? ''}
                           onChange={(e) => setSerieField(item.cle, 'numero_serie', e.target.value)} />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
