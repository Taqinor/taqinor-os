import { useState } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { createLead, updateLead } from '../../features/crm/store/crmSlice'

const STAGE_LABELS = {
  NEW: 'Nouveau',
  CONTACTED: 'Contacté',
  QUOTE_SENT: 'Devis envoyé',
  FOLLOW_UP: 'Relance',
  SIGNED: 'Signé',
  COLD: 'Froid',
}

const STATUT_DEVIS = {
  brouillon: 'Brouillon', envoye: 'Envoyé', accepte: 'Accepté',
  refuse: 'Refusé', expire: 'Expiré',
}

export default function LeadForm({ lead = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const isEdit = !!lead

  const [fields, setFields] = useState({
    nom: lead?.nom ?? '',
    prenom: lead?.prenom ?? '',
    societe: lead?.societe ?? '',
    email: lead?.email ?? '',
    telephone: lead?.telephone ?? '',
    adresse: lead?.adresse ?? '',
    ville: lead?.ville ?? '',
    stage: lead?.stage ?? 'NEW',
    note: lead?.note ?? '',
    facture_hiver: lead?.facture_hiver ?? '',
    facture_ete: lead?.facture_ete ?? '',
    ete_differente: lead?.ete_differente ?? false,
  })
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  const set = (k, v) => setFields(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!fields.nom.trim()) { setErrors({ nom: 'Nom requis' }); return }
    setSaving(true)
    try {
      const payload = {
        ...fields,
        prenom: fields.prenom || null,
        societe: fields.societe || null,
        email: fields.email || null,
        telephone: fields.telephone || null,
        adresse: fields.adresse || null,
        ville: fields.ville || null,
        note: fields.note || null,
        facture_hiver: fields.facture_hiver !== '' ? fields.facture_hiver : null,
        // toggle OFF → la valeur unique vaut hiver ET été : on ne stocke pas d'été
        facture_ete: (fields.ete_differente && fields.facture_ete !== '')
          ? fields.facture_ete : null,
      }
      if (isEdit) {
        await dispatch(updateLead({ id: lead.id, data: payload })).unwrap()
      } else {
        await dispatch(createLead(payload)).unwrap()
      }
      onSaved?.()
      onClose()
    } catch (err) {
      setErrors(typeof err === 'object' ? err : { submit: String(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            {isEdit ? `Éditer — ${lead.nom} ${lead.prenom || ''}` : 'Nouveau lead'}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="modal-body">
            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Nom <span className="req">*</span></label>
                <input className={`form-control${errors.nom ? ' is-invalid' : ''}`}
                       value={fields.nom} onChange={e => set('nom', e.target.value)} />
                {errors.nom && <div className="form-feedback">{errors.nom}</div>}
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Prénom</label>
                <input className="form-control" value={fields.prenom}
                       onChange={e => set('prenom', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Stade</label>
                <select className="form-select" value={fields.stage}
                        onChange={e => set('stage', e.target.value)}>
                  {Object.entries(STAGE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Société</label>
                <input className="form-control" value={fields.societe}
                       onChange={e => set('societe', e.target.value)} />
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Email</label>
                <input type="email" className="form-control" value={fields.email}
                       onChange={e => set('email', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Téléphone</label>
                <input className="form-control" value={fields.telephone}
                       onChange={e => set('telephone', e.target.value)} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Adresse</label>
                <input className="form-control" value={fields.adresse}
                       onChange={e => set('adresse', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Ville</label>
                <input className="form-control" value={fields.ville}
                       onChange={e => set('ville', e.target.value)} />
              </div>
            </div>

            {/* ── Facture électrique + bascule été ── */}
            <div className="form-section">
              <div className="form-section-header">
                <span className="form-section-title">💡 Facture électrique (MAD/mois)</span>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">
                    {fields.ete_differente ? 'Facture Hiver' : 'Facture mensuelle'}
                  </label>
                  <input type="number" min="0" step="any" className="form-control"
                         placeholder="ex: 650" value={fields.facture_hiver}
                         onChange={e => set('facture_hiver', e.target.value)} />
                </div>
                <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                  <label className="pdf-toggle">
                    <input type="checkbox" checked={fields.ete_differente}
                           onChange={e => set('ete_differente', e.target.checked)} />
                    <span>L'été est différent de l'hiver ?</span>
                  </label>
                </div>
                {fields.ete_differente && (
                  <div className="form-group">
                    <label className="form-label">Facture Été</label>
                    <input type="number" min="0" step="any" className="form-control"
                           placeholder="ex: 420" value={fields.facture_ete}
                           onChange={e => set('facture_ete', e.target.value)} />
                  </div>
                )}
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Note</label>
              <textarea className="form-control" rows={2} value={fields.note}
                        onChange={e => set('note', e.target.value)} />
            </div>

            {/* ── Devis empilés sur ce lead ── */}
            {isEdit && (
              <div className="form-section">
                <div className="form-section-header">
                  <span className="form-section-title">
                    📄 Devis de ce lead {lead.client_nom ? `— client : ${lead.client_nom}` : ''}
                  </span>
                </div>
                {(lead.devis ?? []).length === 0 ? (
                  <p className="gen-hint">Aucun devis pour ce lead.</p>
                ) : (
                  <table className="lines-table">
                    <thead>
                      <tr><th>Référence</th><th>Statut</th><th className="col-num">Total TTC</th><th>Créé le</th></tr>
                    </thead>
                    <tbody>
                      {lead.devis.map(d => (
                        <tr key={d.id} style={{ cursor: 'pointer' }}
                            onClick={() => navigate('/ventes/devis')}>
                          <td><strong>{d.reference}</strong></td>
                          <td>{STATUT_DEVIS[d.statut] ?? d.statut}</td>
                          <td className="ta-right">
                            {Math.round(parseFloat(d.total_ttc)).toLocaleString('fr-MA')} DH
                          </td>
                          <td>{new Date(d.date_creation).toLocaleDateString('fr-FR')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {errors.submit && <div className="form-error-box">{errors.submit}</div>}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Enregistrement...' : (isEdit ? 'Mettre à jour' : 'Créer le lead')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
