// N51/N52 — Relevés de production d'un système installé (parc).
// Saisie MANUELLE par défaut (repli quand aucun monitoring n'est configuré).
// Affiche la synthèse (total relevé / attendu / performance %), la liste des
// relevés, et un repère de SOUS-PERFORMANCE (N52) quand un seuil est configuré.
import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import installationsApi from '../../api/installationsApi'

const fmt = (n) => Number(n || 0).toLocaleString('fr-MA')
const todayISO = () => new Date().toISOString().slice(0, 10)

export default function ChantierProduction({ installationId, onChanged }) {
  const role = useSelector((s) => s.auth.role)
  const canWrite = role === 'admin' || role === 'responsable'
  const [data, setData] = useState(null)
  const [form, setForm] = useState({
    periode_debut: '', periode_fin: '', kwh_produit: '', note: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = () => {
    installationsApi.getProduction(installationId)
      .then((r) => setData(r.data)).catch(() => {})
  }
  useEffect(() => { load() }, [installationId]) // eslint-disable-line react-hooks/exhaustive-deps

  const add = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.periode_debut || !form.periode_fin || form.kwh_produit === '') {
      setError('Période et kWh requis.'); return
    }
    setBusy(true)
    try {
      await installationsApi.addProduction(installationId, form)
      setForm({ periode_debut: '', periode_fin: '', kwh_produit: '', note: '' })
      load()
      onChanged && onChanged()
    } catch {
      setError('Impossible d’ajouter le relevé.')
    } finally { setBusy(false) }
  }

  const remove = async (releveId) => {
    if (!window.confirm('Supprimer ce relevé ?')) return
    try { await installationsApi.deleteProduction(installationId, releveId); load() } catch { /* */ }
  }

  const summary = data?.summary
  const releves = data?.releves ?? []
  const perf = summary?.performance_pct
  const sousPerf = summary?.sous_performance // N52 (présent si seuil configuré)

  return (
    <div className="form-section">
      <div className="form-section-header">
        <span className="form-section-title">⚡ Production (suivi)</span>
      </div>

      {summary && (
        <p className="gen-hint" style={{ marginBottom: 10 }}>
          Total relevé : <strong>{fmt(summary.total_kwh)} kWh</strong>
          {summary.total_attendu_kwh != null && (
            <> · attendu : {fmt(summary.total_attendu_kwh)} kWh</>
          )}
          {perf != null && (
            <> · performance : <strong style={{ color: sousPerf ? '#dc2626' : '#16a34a' }}>{perf} %</strong></>
          )}
        </p>
      )}
      {sousPerf && (
        <div className="form-error-box" role="alert" style={{ marginBottom: 10 }}>
          ⚠ Système en sous-performance (seuil : {summary.seuil_pct} %).
          {summary.ticket_cree && ' Un ticket SAV a été créé.'}
        </div>
      )}

      {releves.length === 0 ? (
        <p className="gen-hint">
          Aucun relevé. Saisissez la production relevée au compteur (repli
          manuel — aucun monitoring requis).
        </p>
      ) : (
        <table className="lines-table" style={{ marginBottom: 10 }}>
          <thead>
            <tr><th>Début</th><th>Fin</th><th>kWh</th><th>Source</th><th></th></tr>
          </thead>
          <tbody>
            {releves.map((r) => (
              <tr key={r.id}>
                <td>{r.periode_debut}</td>
                <td>{r.periode_fin}</td>
                <td>{fmt(r.kwh_produit)}</td>
                <td>{r.source_label}</td>
                <td>
                  {canWrite && (
                    <button type="button" className="btn btn-xs btn-outline"
                            onClick={() => remove(r.id)}>✕</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {canWrite && (
        <form onSubmit={add} noValidate style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-end' }}>
          <label style={{ fontSize: 12 }}>Début
            <input type="date" className="form-input" max={todayISO()}
                   value={form.periode_debut}
                   onChange={(e) => setForm({ ...form, periode_debut: e.target.value })} />
          </label>
          <label style={{ fontSize: 12 }}>Fin
            <input type="date" className="form-input" max={todayISO()}
                   value={form.periode_fin}
                   onChange={(e) => setForm({ ...form, periode_fin: e.target.value })} />
          </label>
          <label style={{ fontSize: 12 }}>kWh produit
            <input type="number" step="any" className="form-input" style={{ width: 120 }}
                   value={form.kwh_produit}
                   onChange={(e) => setForm({ ...form, kwh_produit: e.target.value })} />
          </label>
          <button type="submit" className="btn btn-sm btn-primary" disabled={busy}>
            {busy ? '…' : 'Ajouter le relevé'}
          </button>
          {error && <span className="form-error" style={{ color: '#dc2626' }}>{error}</span>}
        </form>
      )}
    </div>
  )
}
