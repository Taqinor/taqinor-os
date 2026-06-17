// T16 — contrats de maintenance (visites préventives). Liste + vue « à venir »
// (visites dues) + génération à la demande des tickets SAV préventifs (sans
// planificateur, cohérent T7). Création simple (client + périodicité + début).
import { useEffect, useState } from 'react'
import savApi from '../../api/savApi'
import crmApi from '../../api/crmApi'
import { openPdfBlob } from '../../utils/pdfBlob'

const PERIODES = [
  ['mensuel', 'Mensuel'], ['trimestriel', 'Trimestriel'],
  ['semestriel', 'Semestriel'], ['annuel', 'Annuel'],
]

export function Component() {
  const [rows, setRows] = useState([])
  const [clients, setClients] = useState([])
  const [dueOnly, setDueOnly] = useState(false)
  const [msg, setMsg] = useState(null)
  const [form, setForm] = useState({
    client: '', periodicite: 'annuel', date_debut: '', date_renouvellement: '' })

  const load = () => savApi.getContrats(dueOnly ? { due: 1 } : {})
    .then(r => setRows(r.data.results ?? r.data)).catch(() => {})

  useEffect(() => { load() }, [dueOnly])
  useEffect(() => {
    crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const create = async () => {
    if (!form.client || !form.date_debut) return
    try {
      const payload = { ...form }
      if (!payload.date_renouvellement) delete payload.date_renouvellement
      await savApi.saveContrat(null, payload)
      setForm({
        client: '', periodicite: 'annuel', date_debut: '',
        date_renouvellement: '' })
      load()
    } catch (e) { setMsg(e?.response?.data?.detail ?? 'Création impossible.') }
  }
  const rapport = async (id) => {
    try {
      const res = await savApi.maintenanceRapportPdf(id)
      openPdfBlob(res.data, `maintenance-contrat-${id}.pdf`)
    } catch { setMsg('Rapport indisponible.') }
  }
  const generer = async () => {
    try {
      const { data } = await savApi.genererVisitesDues()
      setMsg(`${data.tickets_generes} ticket(s) de maintenance généré(s).`)
      load()
    } catch { setMsg('Génération impossible.') }
  }

  return (
    <div className="page" style={{ maxWidth: 1000 }}>
      <div className="page-header">
        <h2>Contrats de maintenance</h2>
        <div className="page-header-actions">
          <button className={`btn btn-sm${dueOnly ? ' btn-primary' : ' btn-outline'}`}
                  onClick={() => setDueOnly(v => !v)}>
            {dueOnly ? 'Tous' : 'À venir (dus)'}
          </button>
          <button className="btn btn-sm btn-outline" onClick={generer}>
            ⚙ Générer les visites dues
          </button>
        </div>
      </div>

      {msg && <div className="alert alert-info" style={{ background: '#ecfdf5', border: '1px solid #6ee7b7', color: '#065f46', borderRadius: 8, padding: '0.6rem 0.85rem', marginBottom: 12 }}>{msg}</div>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16, alignItems: 'flex-end' }}>
        <select className="form-control" style={{ maxWidth: 220 }} value={form.client}
                onChange={e => setForm(f => ({ ...f, client: e.target.value }))}>
          <option value="">— Client —</option>
          {clients.map(c => <option key={c.id} value={c.id}>{c.nom} {c.prenom || ''}</option>)}
        </select>
        <select className="form-control" style={{ maxWidth: 160 }} value={form.periodicite}
                onChange={e => setForm(f => ({ ...f, periodicite: e.target.value }))}>
          {PERIODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <input type="date" className="form-control" style={{ maxWidth: 170 }} value={form.date_debut}
               onChange={e => setForm(f => ({ ...f, date_debut: e.target.value }))} />
        <input type="date" className="form-control" style={{ maxWidth: 170 }}
               title="Date de renouvellement (optionnel)"
               value={form.date_renouvellement}
               onChange={e => setForm(f => ({ ...f, date_renouvellement: e.target.value }))} />
        <button className="btn btn-primary" onClick={create}>+ Ajouter</button>
      </div>

      <table className="data-table">
        <thead>
          <tr><th>Client</th><th>Périodicité</th><th>Début</th><th>Prochaine visite</th><th>Renouvellement</th><th>Statut</th><th></th></tr>
        </thead>
        <tbody>
          {rows.map(c => (
            <tr key={c.id}>
              <td>{c.client_nom}</td>
              <td>{c.periodicite}</td>
              <td>{c.date_debut}</td>
              <td>{c.prochaine_visite}</td>
              <td>
                {c.date_renouvellement || '—'}
                {c.renouvellement_du && <span className="badge" style={{ marginLeft: 6, background: '#fef3c7', color: '#92400e' }}>à renouveler</span>}
              </td>
              <td>
                {!c.actif ? <span className="badge" style={{ background: '#e2e8f0', color: '#475569' }}>Inactif</span>
                  : c.due ? <span className="badge" style={{ background: '#fee2e2', color: '#b91c1c' }}>Visite due</span>
                    : <span className="badge" style={{ background: '#dcfce7', color: '#15803d' }}>À jour</span>}
              </td>
              <td>
                <button className="btn btn-sm btn-outline" onClick={() => rapport(c.id)}>⬇ Rapport PDF</button>
              </td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan={7} style={{ color: '#94a3b8' }}>Aucun contrat.</td></tr>}
        </tbody>
      </table>
    </div>
  )
}
