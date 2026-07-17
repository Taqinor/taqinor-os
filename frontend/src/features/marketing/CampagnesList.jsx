import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'
import CampagneForm, { emptyForm, formFromCampagne } from './CampagneForm'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   NTMKT2 — Liste des campagnes (statut/canal, filtre) + éditeur inline.
   ----------------------------------------------------------------------------
   Remplace l'ancien écran combiné `CampagnesScreen.jsx` (conservé tel quel,
   plus routé — dérogation « touch only the named files ») par une liste
   filtrable + `CampagneForm.jsx` pour la création/édition ; le clic sur une
   ligne ouvre `CampagneDetail.jsx` (trace destinataire XMKT2, test A/B
   NTMKT3, envoi de test XMKT13).
   ========================================================================== */

const STATUTS = [
  { key: '', label: 'Tous les statuts' },
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'en_file', label: 'En file' },
  { key: 'envoi_en_cours', label: 'Envoi en cours' },
  { key: 'envoyee', label: 'Envoyée' },
  { key: 'annulee', label: 'Annulée' },
]
const CANAUX = [
  { key: '', label: 'Tous les canaux' },
  { key: 'email', label: 'Email' },
  { key: 'sms', label: 'SMS' },
  { key: 'whatsapp', label: 'WhatsApp' },
]

export default function CampagnesList() {
  const navigate = useNavigate()
  const [campagnes, setCampagnes] = useState([])
  const [loading, setLoading] = useState(true)
  const [statut, setStatut] = useState('')
  const [canal, setCanal] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null) // null = création
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.campagnes.list()
      .then(r => setCampagnes(marketingApi.unwrapList(r)))
      .catch(() => setCampagnes([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const visibles = campagnes.filter(c => {
    if (statut && c.statut !== statut) return false
    if (canal && c.canal !== canal) return false
    return true
  })

  const startCreate = () => { setEditing(null); setShowForm(true) }
  const startEdit = (c) => { setEditing(c); setShowForm(true); }
  const closeForm = () => { setShowForm(false); setEditing(null); setErr('') }

  const save = async (payload) => {
    if (editing) await marketingApi.campagnes.update(editing.id, payload)
    else await marketingApi.campagnes.create(payload)
    closeForm()
    load()
  }

  return (
    <div className="page">
      <div className="page-header" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
        <h2>Campagnes marketing</h2>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <select className="form-input" data-testid="campagnes-filtre-statut"
            value={statut} onChange={e => setStatut(e.target.value)}>
            {STATUTS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
          <select className="form-input" data-testid="campagnes-filtre-canal"
            value={canal} onChange={e => setCanal(e.target.value)}>
            {CANAUX.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
          {!showForm && (
            <button className="btn btn-primary" data-testid="campagnes-nouvelle"
              onClick={startCreate}>Nouvelle campagne</button>
          )}
        </div>
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      {showForm && (
        <div style={{ marginBottom: '1.25rem' }}>
          <CampagneForm
            initial={editing ? formFromCampagne(editing) : emptyForm()}
            editing={!!editing}
            onSave={save}
            onCancel={closeForm} />
        </div>
      )}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="campagnes-table">
            <thead>
              <tr>
                <th>Nom</th><th>Canal</th><th>Statut</th>
                <th>Planifiée le</th><th>Envoyés</th><th>Ouverture %</th><th />
              </tr>
            </thead>
            <tbody>
              {visibles.map(c => (
                <tr key={c.id} data-testid="campagne-row"
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/marketing/campagnes/${c.id}`)}>
                  <td>{c.nom}</td>
                  <td>{c.canal_display || c.canal}</td>
                  <td>{c.statut_display || c.statut}</td>
                  <td>{c.planifiee_le ? formatDateTime(c.planifiee_le) : '—'}</td>
                  <td>{c.nb_envois ?? 0}</td>
                  <td>{c.taux_ouverture_pct ?? 0}%</td>
                  <td>
                    <button className="btn btn-light" type="button"
                      data-testid="campagne-editer"
                      onClick={(e) => { e.stopPropagation(); startEdit(c) }}>
                      Éditer
                    </button>
                  </td>
                </tr>
              ))}
              {visibles.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center',
                  color: '#64748b' }}>Aucune campagne</td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
