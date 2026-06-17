import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import stockApi from '../../api/stockApi'
import {
  OUTIL_EMPLACEMENTS, OUTIL_STATUTS,
  emplacementLabel, statutMeta, filterOutillage,
} from '../../features/stock/outillage'

// F1 — Catalogue Outillage (équipement durable). Séparé des SKU vendables :
// un outil n'est jamais vendu, consommé, ni mis sur un document client.

const fmtDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

function StatutBadge({ statut }) {
  const m = statutMeta(statut)
  return (
    <span className="badge" style={{
      background: `${m.color}22`, color: m.color, padding: '2px 8px',
      borderRadius: 6, fontSize: 12, whiteSpace: 'nowrap', fontWeight: 600,
    }}>{m.label}</span>
  )
}

export default function OutillagePage() {
  const role = useSelector(s => s.auth.role)
  const permissions = useSelector(s => s.auth.permissions)
  const canEdit = permissions.length
    ? permissions.includes('stock_modifier')
    : (role === 'responsable' || role === 'admin')

  const [list, setList]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [search, setSearch]   = useState('')
  const [emplacement, setEmpl] = useState('')
  const [statut, setStatut]   = useState('')
  const [editing, setEditing] = useState(null) // null=none, {}=new, {…}=edit

  // Recharge la liste. setState uniquement dans les callbacks async (jamais
  // synchrone dans le corps de l'effet — règle react-hooks/set-state-in-effect).
  const reload = () =>
    stockApi.getOutillage()
      .then(r => { setList(r.data); setError(null) })
      .catch(e => setError(e?.response?.data ?? e.message))
      .finally(() => setLoading(false))
  useEffect(() => { reload() }, [])

  const filtered = useMemo(
    () => filterOutillage(list, { search, emplacement, statut }),
    [list, search, emplacement, statut])

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Outillage
          {list.length > 0 && <span className="count-badge">{list.length}</span>}
        </h2>
        <div className="page-header-actions">
          <input
            className="search-input" type="search"
            placeholder="Nom, catégorie, asset tag, n° série…"
            value={search} onChange={e => setSearch(e.target.value)}
          />
          {canEdit && (
            <button className="btn btn-primary" onClick={() => setEditing({})}>
              + Ajouter un outil
            </button>
          )}
        </div>
      </div>

      <p className="text-muted" style={{ marginTop: -8, fontSize: 13 }}>
        Équipement durable suivi à travers dépôt, camionnette et chantiers —
        séparé du stock vendable, jamais consommé ni facturé.
      </p>

      <div className="filter-bar" style={{ display: 'flex', gap: 12, margin: '12px 0' }}>
        <select className="form-select" value={emplacement}
                onChange={e => setEmpl(e.target.value)} style={{ maxWidth: 220 }}>
          <option value="">Tous les emplacements</option>
          {OUTIL_EMPLACEMENTS.map(e => (
            <option key={e.key} value={e.key}>{e.label}</option>
          ))}
        </select>
        <select className="form-select" value={statut}
                onChange={e => setStatut(e.target.value)} style={{ maxWidth: 220 }}>
          <option value="">Tous les statuts</option>
          {OUTIL_STATUTS.map(s => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
      </div>

      {loading && <p className="page-loading">Chargement de l'outillage…</p>}
      {error && <p className="page-error">Erreur : {JSON.stringify(error)}</p>}

      {!loading && !error && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Nom</th>
              <th>Catégorie</th>
              <th>Asset tag</th>
              <th>N° série</th>
              <th>Emplacement</th>
              <th>Statut</th>
              <th>Achat</th>
              {canEdit && <th></th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map(o => (
              <tr key={o.id}>
                <td><strong>{o.nom}</strong></td>
                <td>{o.categorie || <span className="text-muted">—</span>}</td>
                <td><span className="mono-text">{o.asset_tag || <span className="text-muted">—</span>}</span></td>
                <td><span className="mono-text">{o.numero_serie || <span className="text-muted">—</span>}</span></td>
                <td>{emplacementLabel(o.emplacement)}</td>
                <td><StatutBadge statut={o.statut} /></td>
                <td className="text-muted">{fmtDateFR(o.date_achat)}</td>
                {canEdit && (
                  <td className="ta-right">
                    <button className="btn btn-sm btn-outline"
                            onClick={() => setEditing(o)}>Modifier</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!loading && !error && filtered.length === 0 && (
        <p className="empty-state">
          {search || emplacement || statut
            ? 'Aucun outil ne correspond aux filtres.'
            : 'Aucun outil enregistré. Ajoutez votre premier outil.'}
        </p>
      )}

      {editing && (
        <OutilForm
          outil={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); reload() }}
        />
      )}
    </div>
  )
}

// ── Formulaire outil ────────────────────────────────────────────────────────

function OutilForm({ outil, onClose, onSaved }) {
  const isNew = !outil?.id
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const [f, setF] = useState({
    nom:          outil?.nom ?? '',
    categorie:    outil?.categorie ?? '',
    asset_tag:    outil?.asset_tag ?? '',
    numero_serie: outil?.numero_serie ?? '',
    emplacement:  outil?.emplacement ?? 'depot',
    statut:       outil?.statut ?? 'disponible',
    date_achat:   outil?.date_achat ?? '',
  })
  const set = (k, v) => setF(s => ({ ...s, [k]: v }))

  const submit = async (e) => {
    e.preventDefault()
    if (!f.nom.trim()) { setErrors({ nom: 'Nom requis' }); return }
    setSaving(true)
    const payload = { ...f, date_achat: f.date_achat || null }
    try {
      if (isNew) await stockApi.createOutil(payload)
      else await stockApi.updateOutil(outil.id, payload)
      onSaved()
    } catch (err) {
      const data = err?.response?.data ?? {}
      setErrors(typeof data === 'object'
        ? Object.fromEntries(Object.entries(data).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]))
        : { submit: String(data) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">{isNew ? 'Ajouter un outil' : 'Modifier l\'outil'}</h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={submit}>
          <div className="modal-body">
            <div className="form-group">
              <label className="form-label">Nom <span className="req">*</span></label>
              <input className={`form-control${errors.nom ? ' is-invalid' : ''}`}
                     value={f.nom} onChange={e => set('nom', e.target.value)}
                     placeholder="Perceuse, échelle, multimètre…" />
              {errors.nom && <div className="form-feedback">{errors.nom}</div>}
            </div>
            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Catégorie</label>
                <input className="form-control" value={f.categorie}
                       onChange={e => set('categorie', e.target.value)}
                       placeholder="Électroportatif, mesure, accès…" />
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Asset tag</label>
                <input className={`form-control${errors.asset_tag ? ' is-invalid' : ''}`}
                       value={f.asset_tag} onChange={e => set('asset_tag', e.target.value)}
                       placeholder="TAQ-001" />
                {errors.asset_tag && <div className="form-feedback">{errors.asset_tag}</div>}
              </div>
            </div>
            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">N° de série</label>
                <input className="form-control" value={f.numero_serie}
                       onChange={e => set('numero_serie', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Date d'achat</label>
                <input type="date" className="form-control" value={f.date_achat}
                       onChange={e => set('date_achat', e.target.value)} />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Emplacement</label>
                <select className="form-select" value={f.emplacement}
                        onChange={e => set('emplacement', e.target.value)}>
                  {OUTIL_EMPLACEMENTS.map(e => (
                    <option key={e.key} value={e.key}>{e.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Statut</label>
                <select className="form-select" value={f.statut}
                        onChange={e => set('statut', e.target.value)}>
                  {OUTIL_STATUTS.map(s => (
                    <option key={s.key} value={s.key}>{s.label}</option>
                  ))}
                </select>
              </div>
            </div>
            {errors.submit && <div className="form-error-box">{errors.submit}</div>}
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose}>Annuler</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Enregistrement…' : (isNew ? 'Ajouter' : 'Enregistrer')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
