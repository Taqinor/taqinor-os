import { useEffect, useMemo, useState } from 'react'
import savApi from '../../api/savApi'
import installationsApi from '../../api/installationsApi'
import { EMPTY_CONTRAT_FILTERS, filterContrats } from '../../features/sav/contrat'

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// Badge d'échéance : due (rouge), bientôt (orange), planifiée (vert).
function EcheanceBadge({ contrat }) {
  let color = '#16a34a'
  let label = `Prochaine visite : ${formatDateFR(contrat.prochaine_visite)}`
  if (contrat.est_due) {
    color = '#dc2626'
    const n = contrat.jours_avant_visite
    label = n != null && n < 0 ? `Visite due (en retard de ${-n} j)` : 'Visite due'
  } else if (contrat.est_a_venir) {
    color = '#d97706'
    label = `À venir dans ${contrat.jours_avant_visite} j`
  }
  return (
    <span className="badge" style={{
      background: `${color}22`, color, padding: '2px 8px',
      borderRadius: 6, fontSize: 12, whiteSpace: 'nowrap',
    }}>{label}</span>
  )
}

function ContratForm({ contrat, onClose, onSaved }) {
  const isNew = !contrat?.id
  const [installations, setInstallations] = useState([])
  const [fields, setFields] = useState({
    installation: contrat?.installation ?? '',
    libelle: contrat?.libelle ?? '',
    intervalle_mois: contrat?.intervalle_mois ?? 12,
    date_debut: contrat?.date_debut ?? '',
    derniere_visite: contrat?.derniere_visite ?? '',
    actif: contrat?.actif ?? true,
    notes: contrat?.notes ?? '',
  })
  const set = (k, v) => setFields((f) => ({ ...f, [k]: v }))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    installationsApi.getInstallations()
      .then((r) => setInstallations(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }, [])

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const nullable = (v) => (v === '' || v === undefined ? null : v)
      const data = {
        installation: fields.installation,
        libelle: nullable(fields.libelle),
        intervalle_mois: fields.intervalle_mois,
        date_debut: fields.date_debut,
        derniere_visite: nullable(fields.derniere_visite),
        actif: fields.actif,
        notes: nullable(fields.notes),
      }
      if (isNew) await savApi.createContrat(data)
      else await savApi.updateContrat(contrat.id, data)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(JSON.stringify(err.response?.data ?? err.message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            {isNew ? 'Nouveau contrat de maintenance' : `Contrat — ${contrat.libelle ?? ''}`}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <div className="form-row">
            <div className="form-group fg-grow">
              <label className="form-label">Chantier</label>
              {isNew ? (
                <select className="form-select" value={fields.installation}
                        onChange={(e) => set('installation', e.target.value)}>
                  <option value="">— Sélectionner un chantier —</option>
                  {installations.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.reference} — {i.client_nom ?? ''}
                    </option>
                  ))}
                </select>
              ) : (
                <input className="form-control"
                       value={contrat.installation_reference ?? '—'} readOnly />
              )}
            </div>
            <div className="form-group">
              <label className="form-label">Client</label>
              <input className="form-control"
                     value={contrat.client_nom ?? '(défini par le chantier)'} readOnly />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group fg-grow">
              <label className="form-label">Libellé</label>
              <input className="form-control" value={fields.libelle}
                     placeholder="ex. Maintenance annuelle onduleur"
                     onChange={(e) => set('libelle', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Intervalle (mois)</label>
              <input type="number" step="any" className="form-control"
                     value={fields.intervalle_mois}
                     onChange={(e) => set('intervalle_mois', e.target.value)} />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Date de début</label>
              <input type="date" className="form-control" value={fields.date_debut}
                     onChange={(e) => set('date_debut', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Dernière visite</label>
              <input type="date" className="form-control" value={fields.derniere_visite}
                     onChange={(e) => set('derniere_visite', e.target.value)} />
            </div>
            <div className="form-group" style={{ alignSelf: 'flex-end' }}>
              <label className="form-label">
                <input type="checkbox" checked={fields.actif}
                       onChange={(e) => set('actif', e.target.checked)} /> Actif
              </label>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Notes</label>
            <textarea className="form-control" rows={2} value={fields.notes}
                      onChange={(e) => set('notes', e.target.value)} />
          </div>
          {error && <div className="form-error-box" role="alert">{error}</div>}
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={onClose}>Fermer</button>
          <button type="button" className="btn btn-primary" disabled={saving}
                  onClick={save}>
            {saving ? 'Enregistrement...' : 'Enregistrer'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ContratsMaintenancePage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(EMPTY_CONTRAT_FILTERS)
  const [editing, setEditing] = useState(null)
  const [creating, setCreating] = useState(false)

  const setF = (k, v) => setFilters((f) => ({ ...f, [k]: v }))
  const reload = () =>
    savApi.getContrats()
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  useEffect(() => { reload() }, [])

  const rows = useMemo(() => filterContrats(items, filters), [items, filters])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Contrats de maintenance</h1>
        <div className="page-subtitle">{rows.length} contrat(s)</div>
        <button type="button" className="btn btn-primary"
                onClick={() => setCreating(true)}>
          + Nouveau contrat
        </button>
      </div>

      <div className="filter-bar" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <input className="form-control" placeholder="Rechercher (libellé, client, chantier)…"
               value={filters.q} onChange={(e) => setF('q', e.target.value)} style={{ flex: '1 1 220px' }} />
        <select className="form-select" value={filters.actif} onChange={(e) => setF('actif', e.target.value)}>
          <option value="">Tous</option>
          <option value="true">Actifs</option>
          <option value="false">Inactifs</option>
        </select>
      </div>

      {loading ? (
        <p className="gen-hint">Chargement…</p>
      ) : rows.length === 0 ? (
        <p className="gen-hint">Aucun contrat de maintenance.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Libellé</th>
                <th>Client</th>
                <th className="m-hide">Chantier</th>
                <th className="m-hide">Intervalle</th>
                <th>Prochaine visite</th>
                <th className="m-hide">Actif</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} onClick={() => setEditing(c)} style={{ cursor: 'pointer' }}>
                  <td>{c.libelle ?? '—'}</td>
                  <td>{c.client_nom ?? '—'}</td>
                  <td className="m-hide">{c.installation_reference ?? '—'}</td>
                  <td className="m-hide">{c.intervalle_mois} mois</td>
                  <td><EcheanceBadge contrat={c} /></td>
                  <td className="m-hide">{c.actif ? 'Oui' : 'Non'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating && (
        <ContratForm onClose={() => setCreating(false)} onSaved={reload} />
      )}
      {editing && (
        <ContratForm contrat={editing} onClose={() => setEditing(null)} onSaved={reload} />
      )}
    </div>
  )
}
