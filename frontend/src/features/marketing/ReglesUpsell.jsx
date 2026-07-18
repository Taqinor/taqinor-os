import { useEffect, useState, useCallback } from 'react'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   NTMKT9 — Règles d'upsell / cross-sell (FG241).
   ----------------------------------------------------------------------------
   `marketing/regles-upsell/` — CRUD simple : déclencheur de contexte →
   produit/service suggéré + message commercial + priorité.
   ========================================================================== */

const DECLENCHEURS = [
  { key: 'sans_batterie', label: 'Client sans batterie' },
  { key: 'site_unique', label: 'Un seul site équipé' },
  { key: 'sans_contrat_om', label: 'Sans contrat O&M' },
  { key: 'installation_ancienne', label: 'Installation ancienne' },
]

const EMPTY = { declencheur: 'sans_batterie', produit_suggere: '', message: '', priorite: 0 }

export default function ReglesUpsell() {
  const [regles, setRegles] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(EMPTY)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.reglesUpsell.list()
      .then(r => setRegles(marketingApi.unwrapList(r)))
      .catch(() => setRegles([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const setField = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const creer = async (e) => {
    e.preventDefault()
    setErr('')
    try {
      await marketingApi.reglesUpsell.create({
        ...form, priorite: Number(form.priorite) || 0,
      })
      setForm(EMPTY)
      load()
    } catch {
      setErr('Création impossible.')
    }
  }

  const toggleActif = async (r) => {
    try {
      await marketingApi.reglesUpsell.update(r.id, { actif: !r.actif })
      load()
    } catch {
      setErr('Mise à jour impossible.')
    }
  }

  return (
    <div className="page">
      <div className="page-header"><h2>Règles d'upsell</h2></div>

      <form onSubmit={creer} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap',
        marginBottom: '1rem' }}>
        <select className="form-input" data-testid="regle-declencheur"
          value={form.declencheur} onChange={setField('declencheur')}>
          {DECLENCHEURS.map(d => <option key={d.key} value={d.key}>{d.label}</option>)}
        </select>
        <input className="form-input" data-testid="regle-produit" placeholder="Produit suggéré"
          required value={form.produit_suggere} onChange={setField('produit_suggere')}
          style={{ flex: '1 1 200px' }} />
        <input className="form-input" data-testid="regle-message" placeholder="Message commercial"
          value={form.message} onChange={setField('message')} style={{ flex: '1 1 220px' }} />
        <input type="number" className="form-input" data-testid="regle-priorite"
          placeholder="Priorité" value={form.priorite} onChange={setField('priorite')}
          style={{ maxWidth: 100 }} />
        <button type="submit" className="btn btn-primary" data-testid="regle-creer">Créer</button>
      </form>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="regles-table">
            <thead>
              <tr><th>Déclencheur</th><th>Produit</th><th>Priorité</th><th>Statut</th><th /></tr>
            </thead>
            <tbody>
              {regles.map(r => (
                <tr key={r.id} data-testid="regle-row">
                  <td>{DECLENCHEURS.find(d => d.key === r.declencheur)?.label || r.declencheur}</td>
                  <td>{r.produit_suggere}</td>
                  <td>{r.priorite}</td>
                  <td>{r.actif ? 'Active' : 'Inactive'}</td>
                  <td>
                    <button className="btn btn-light" type="button"
                      data-testid="regle-toggle" onClick={() => toggleActif(r)}>
                      {r.actif ? 'Désactiver' : 'Activer'}
                    </button>
                  </td>
                </tr>
              ))}
              {regles.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune règle
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
