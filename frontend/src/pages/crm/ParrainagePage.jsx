// N98 — programme de parrainage : un client (parrain) recommande un prospect.
// Liste + création + tableau de bord simple (totaux + récompenses). La
// récompense par défaut + l'activation se règlent dans Paramètres.
import { useEffect, useState } from 'react'
import crmApi from '../../api/crmApi'
import { Table } from '../reporting/Table'
import { formatMAD } from '../../lib/format'

const STATUTS = [
  ['en_attente', 'En attente'],
  ['converti', 'Converti'],
  ['recompense_versee', 'Récompense versée'],
]
const dh = (v) => `${formatMAD(v, { withSymbol: false })} DH`

export default function ParrainagePage() {
  // YSERV11 — « ?parrain=<client_id> » pré-remplit le parrain (lien depuis
  // la notification « Client promoteur — proposer le parrainage »).
  // Lu sur window.location (pas de dépendance au contexte Router).
  const parrainInitial = new URLSearchParams(
    typeof window !== 'undefined' ? window.location.search : '',
  ).get('parrain') || ''
  const [rows, setRows] = useState([])
  const [clients, setClients] = useState([])
  const [stats, setStats] = useState(null)
  const [msg, setMsg] = useState(null)
  const [form, setForm] = useState(
    { parrain: parrainInitial, filleul_nom: '', recompense: '' })

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

  // P169 — plus aucun style={} en dur : tout passe par des classes Tailwind/tokens.
  const cardCls = 'stat-card min-w-[150px] rounded-xl border border-border bg-card px-[1.1rem] py-[0.85rem]'
  const lblCls = 'text-[11px] uppercase text-muted-foreground'
  const valCls = 'mt-1 text-xl font-bold text-foreground'

  return (
    <div className="page max-w-[1000px]">
      <div className="page-header"><h2>Parrainage</h2></div>

      {stats && (
        <div className="mb-4 flex flex-wrap gap-3">
          <div className={cardCls}>
            <div className={lblCls}>Parrainages</div>
            <div className={valCls}>{stats.total}</div>
          </div>
          <div className={cardCls}>
            <div className={lblCls}>Convertis</div>
            <div className={valCls}>{stats.par_statut?.converti || 0}</div>
          </div>
          <div className={cardCls}>
            <div className={lblCls}>Récompenses (total)</div>
            <div className={valCls}>{dh(stats.recompenses_total)}</div>
          </div>
          <div className={cardCls}>
            <div className={lblCls}>Récompenses versées</div>
            <div className={valCls}>{dh(stats.recompenses_versees)}</div>
          </div>
        </div>
      )}

      {msg && (
        <div className="alert alert-info mb-3 rounded-lg border border-destructive/30 bg-destructive/12 px-[0.85rem] py-[0.6rem] text-destructive">
          {msg}
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-end gap-2">
        <select className="form-control max-w-[220px]"
                value={form.parrain}
                onChange={e => setForm(f => ({ ...f, parrain: e.target.value }))}>
          <option value="">— Parrain (client) —</option>
          {clients.map(c => (
            <option key={c.id} value={c.id}>{c.nom} {c.prenom || ''}</option>
          ))}
        </select>
        <input className="form-control max-w-[200px]"
               placeholder="Nom du filleul" value={form.filleul_nom}
               onChange={e => setForm(f => ({ ...f, filleul_nom: e.target.value }))} />
        <input className="form-control max-w-[150px]" type="number" min="0" step="any"
               placeholder="Récompense (défaut)"
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
              <select className="form-control max-w-[180px]" value={p.statut}
                      onChange={e => setStatut(p.id, e.target.value)}>
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
