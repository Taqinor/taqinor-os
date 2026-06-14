import { useEffect, useState } from 'react'
import ventesApi from '../../api/ventesApi'
import { openPdfBlob } from '../../utils/pdfBlob'

const dh = (v) => `${Number(v ?? 0).toLocaleString('fr-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MAD`

export default function RelancesPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [target, setTarget] = useState(null)  // facture being relancée
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => {
    setLoading(true)
    ventesApi.getRelances()
      .then(r => setRows(r.data)).catch(() => {}).finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const relancer = async () => {
    setBusy(true)
    try {
      await ventesApi.relancerFacture(target.id, {
        niveau: target.niveau?.ordre, note,
      })
      setTarget(null); setNote(''); load()
    } catch { /* */ } finally { setBusy(false) }
  }
  const exclure = async (r) => {
    if (!window.confirm('Exclure cette facture des relances ?')) return
    try { await ventesApi.exclureRelance(r.id, true); load() } catch { /* */ }
  }
  const lettre = async (r) => {
    try {
      const res = await ventesApi.getLettreRelancePdf(r.id)
      openPdfBlob(res.data, `Relance_${r.reference}.pdf`)
    } catch { alert('PDF indisponible.') }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Relances / Impayés <span className="count-badge">{rows.length}</span></h2>
      </div>
      <p className="gen-hint" style={{ marginBottom: 12 }}>
        Vue de recouvrement — consigner et imprimer uniquement. Aucun envoi
        automatique (email/SMS) n'est effectué.
      </p>
      {loading ? <p className="page-loading">Chargement…</p> : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Facture</th><th>Client</th><th>Échéance</th>
              <th className="ta-right">Dû</th><th>Retard</th><th>Niveau</th>
              <th>Relances</th><th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id}>
                <td><strong>{r.reference}</strong></td>
                <td>{r.client_nom}</td>
                <td style={r.jours_retard > 0 ? { color: '#dc2626', fontWeight: 600 } : undefined}>
                  {r.date_echeance || '—'}
                </td>
                <td className="ta-right">{dh(r.montant_du)}</td>
                <td style={r.jours_retard > 0 ? { color: '#dc2626' } : undefined}>
                  {r.jours_retard > 0 ? `${r.jours_retard} j` : '—'}
                </td>
                <td>{r.niveau ? r.niveau.nom : '—'}</td>
                <td>{r.nb_relances}</td>
                <td className="ta-right">
                  <button className="btn btn-sm btn-primary" onClick={() => { setTarget(r); setNote('') }}>Relancer</button>
                  <button className="btn btn-sm btn-outline" style={{ marginLeft: 6 }} onClick={() => lettre(r)}>Lettre</button>
                  <button className="btn btn-sm btn-outline" style={{ marginLeft: 6 }} onClick={() => exclure(r)}>Exclure</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={8} style={{ textAlign: 'center', color: '#94a3b8', padding: '2rem' }}>
                Aucune facture impayée. 🎉
              </td></tr>
            )}
          </tbody>
        </table>
      )}

      {target && (
        <div className="modal-overlay" onClick={() => setTarget(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Consigner une relance — {target.reference}</h3>
              <button className="modal-close" onClick={() => setTarget(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p className="gen-hint">
                {target.niveau ? `Niveau courant : ${target.niveau.nom}. ` : ''}
                Cette action journalise la relance (aucun envoi).
              </p>
              <div className="form-group">
                <label className="form-label">Note (appel, courrier remis…)</label>
                <textarea className="form-control" rows={3} value={note}
                          onChange={e => setNote(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setTarget(null)}>Annuler</button>
              <button className="btn btn-primary" disabled={busy} onClick={relancer}>
                {busy ? '…' : 'Consigner'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
