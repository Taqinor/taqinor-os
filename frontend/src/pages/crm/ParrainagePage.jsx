// N98 — programme de parrainage : un client (parrain) recommande un prospect.
// Liste + création + tableau de bord simple (totaux + récompenses). La
// récompense par défaut + l'activation se règlent dans Paramètres.
import { useEffect, useState } from 'react'
import crmApi from '../../api/crmApi'
import { Table } from '../reporting/Table'

const STATUTS = [
  ['en_attente', 'En attente'],
  ['converti', 'Converti'],
  ['recompense_versee', 'Récompense versée'],
]
const dh = (v) => `${Number(v ?? 0).toLocaleString('fr-MA')} DH`

export default function ParrainagePage() {
  const [rows, setRows] = useState([])
  const [clients, setClients] = useState([])
  const [stats, setStats] = useState(null)
  const [msg, setMsg] = useState(null)
  const [form, setForm] = useState(
    { parrain: '', filleul_nom: '', recompense: '' })

  const load = () => {
    crmApi.getParrainages()
      .then(r => setRows(r.data.results ?? r.data)).catch(() => {})
    crmApi.parrainageStats().then(r => setStats(r.data)).catch(() => {})
  }
  useEffect(() => { load() }, [])
  useEffect(() => {
    crmApi.getClients()
      .then(r => setClients(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const create = async () => {
    if (!form.parrain) { setMsg('Choisissez un parrain.'); return }
    try {
      const payload = { ...form }
      if (!payload.recompense) delete payload.recompense
      await crmApi.saveParrainage(null, payload)
      setForm({ parrain: '', filleul_nom: '', recompense: '' })
      setMsg(null)
      load()
    } catch (e) { setMsg(e?.response?.data?.detail ?? 'Création impossible.') }
  }
  const setStatut = async (id, statut) => {
    try { await crmApi.saveParrainage(id, { statut }); load() } catch { /* */ }
  }

  return (
    <div className="page" style={{ maxWidth: 1000 }}>
      <div className="page-header"><h2>Parrainage</h2></div>

      {stats && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap',
          marginBottom: 16 }}>
          <div className="stat-card" style={cardS}>
            <div style={lblS}>Parrainages</div>
            <div style={valS}>{stats.total}</div>
          </div>
          <div className="stat-card" style={cardS}>
            <div style={lblS}>Convertis</div>
            <div style={valS}>{stats.par_statut?.converti || 0}</div>
          </div>
          <div className="stat-card" style={cardS}>
            <div style={lblS}>Récompenses (total)</div>
            <div style={valS}>{dh(stats.recompenses_total)}</div>
          </div>
          <div className="stat-card" style={cardS}>
            <div style={lblS}>Récompenses versées</div>
            <div style={valS}>{dh(stats.recompenses_versees)}</div>
          </div>
        </div>
      )}

      {msg && <div className="alert alert-info" style={{ background: '#fef2f2',
        border: '1px solid #fecaca', color: '#b91c1c', borderRadius: 8,
        padding: '0.6rem 0.85rem', marginBottom: 12 }}>{msg}</div>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap',
        marginBottom: 16, alignItems: 'flex-end' }}>
        <select className="form-control" style={{ maxWidth: 220 }}
                value={form.parrain}
                onChange={e => setForm(f => ({ ...f, parrain: e.target.value }))}>
          <option value="">— Parrain (client) —</option>
          {clients.map(c => (
            <option key={c.id} value={c.id}>{c.nom} {c.prenom || ''}</option>
          ))}
        </select>
        <input className="form-control" style={{ maxWidth: 200 }}
               placeholder="Nom du filleul" value={form.filleul_nom}
               onChange={e => setForm(f => ({ ...f, filleul_nom: e.target.value }))} />
        <input className="form-control" type="number" min="0" step="any"
               style={{ maxWidth: 150 }} placeholder="Récompense (défaut)"
               value={form.recompense}
               onChange={e => setForm(f => ({ ...f, recompense: e.target.value }))} />
        <button className="btn btn-primary" onClick={create}>+ Ajouter</button>
      </div>

      {/* P167 — migré vers le moteur de tableau partagé (plus de data-table). */}
      <Table
        aria-label="Parrainages"
        getRowKey={(p) => p.id}
        columns={[
          { key: 'parrain', header: 'Parrain', cell: (p) => p.parrain_nom },
          { key: 'filleul', header: 'Filleul', cell: (p) => p.filleul_nom || '—' },
          { key: 'recompense', header: 'Récompense', cell: (p) => (p.recompense ? dh(p.recompense) : '—') },
          {
            key: 'statut',
            header: 'Statut',
            cell: (p) => (
              <select className="form-control" value={p.statut}
                      onChange={e => setStatut(p.id, e.target.value)}
                      style={{ maxWidth: 180 }}>
                {STATUTS.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            ),
          },
          { key: 'cree', header: 'Créé le', cell: (p) => (p.date_creation || '').slice(0, 10) },
        ]}
        rows={rows}
        empty={<span className="text-muted-foreground">Aucun parrainage.</span>}
      />
    </div>
  )
}

const cardS = {
  background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12,
  padding: '0.85rem 1.1rem', minWidth: 150,
}
const lblS = { fontSize: 11, color: '#64748b', textTransform: 'uppercase' }
const valS = { fontSize: 20, fontWeight: 700, color: '#0d1b3e', marginTop: 4 }
