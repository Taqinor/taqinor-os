import { useState } from 'react'
import { useDispatch } from 'react-redux'
import { createClient, updateClient } from '../../features/crm/store/crmSlice'
import CustomFieldsRenderer from '../../components/customfields/CustomFieldsRenderer'

export default function ClientForm({ client = null, onClose }) {
  const dispatch = useDispatch()
  const isEdit = !!client

  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  const [fields, setFields] = useState({
    nom:         client?.nom         ?? '',
    prenom:      client?.prenom      ?? '',
    email:       client?.email       ?? '',
    telephone:   client?.telephone   ?? '',
    adresse:     client?.adresse     ?? '',
    // Type + identifiants marocains. Par défaut « Entreprise » si un ICE est
    // déjà présent, sinon « Particulier ».
    type_client: client?.type_client ?? (client?.ice ? 'entreprise' : 'particulier'),
    cin:         client?.cin         ?? '',
    ice:         client?.ice         ?? '',
    if_fiscal:   client?.if_fiscal   ?? '',
    rc:          client?.rc          ?? '',
  })
  const [customFields, setCustomFields] = useState(client?.custom_fields ?? {})
  const isEntreprise = fields.type_client === 'entreprise'

  const setField = (k, v) => setFields(f => ({ ...f, [k]: v }))

  const validate = () => {
    const e = {}
    if (!fields.nom.trim()) e.nom = 'Le nom est requis'
    if (!fields.email.trim()) {
      e.email = "L'email est requis"
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email)) {
      e.email = 'Adresse email invalide'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        nom:         fields.nom.trim(),
        prenom:      fields.prenom.trim()    || null,
        email:       fields.email.trim(),
        telephone:   fields.telephone.trim() || null,
        adresse:     fields.adresse.trim()   || null,
        type_client: fields.type_client,
        // On envoie le jeu pertinent ; l'autre est vidé pour rester cohérent.
        cin:       isEntreprise ? null : (fields.cin.trim() || null),
        ice:       isEntreprise ? (fields.ice.trim() || null) : null,
        if_fiscal: isEntreprise ? (fields.if_fiscal.trim() || null) : null,
        rc:        isEntreprise ? (fields.rc.trim() || null) : null,
        custom_fields: customFields,
      }
      if (isEdit) {
        await dispatch(updateClient({ id: client.id, data: payload })).unwrap()
      } else {
        await dispatch(createClient(payload)).unwrap()
      }
      onClose()
    } catch (err) {
      // Map DRF field errors back to form fields
      const e = {}
      if (err?.email)  e.email  = Array.isArray(err.email)  ? err.email[0]  : err.email
      if (err?.nom)    e.nom    = Array.isArray(err.nom)    ? err.nom[0]    : err.nom
      if (!e.email && !e.nom) {
        e.submit = err?.detail ?? JSON.stringify(err)
      }
      setErrors(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            {isEdit ? 'Éditer le client' : 'Nouveau client'}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Nom <span className="req">*</span></label>
                <input
                  className={`form-control${errors.nom ? ' is-invalid' : ''}`}
                  value={fields.nom}
                  onChange={e => setField('nom', e.target.value)}
                  placeholder="Dupont"
                  autoFocus
                />
                {errors.nom && <div className="form-feedback">{errors.nom}</div>}
              </div>

              <div className="form-group fg-grow">
                <label className="form-label">Prénom</label>
                <input
                  className="form-control"
                  value={fields.prenom}
                  onChange={e => setField('prenom', e.target.value)}
                  placeholder="Jean"
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Email <span className="req">*</span></label>
              <input
                type="email"
                className={`form-control${errors.email ? ' is-invalid' : ''}`}
                value={fields.email}
                onChange={e => setField('email', e.target.value)}
                placeholder="jean.dupont@exemple.com"
              />
              {errors.email && <div className="form-feedback">{errors.email}</div>}
            </div>

            <div className="form-group">
              <label className="form-label">Téléphone</label>
              <input
                type="tel"
                className="form-control"
                value={fields.telephone}
                onChange={e => setField('telephone', e.target.value)}
                placeholder="+212 6 XX XX XX XX"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Type de client</label>
              <select
                className="form-control"
                value={fields.type_client}
                onChange={e => setField('type_client', e.target.value)}
              >
                <option value="particulier">Particulier</option>
                <option value="entreprise">Entreprise</option>
              </select>
            </div>

            {/* Identifiants selon le type : CIN pour un particulier,
                ICE / IF / RC pour une entreprise. */}
            {isEntreprise ? (
              <>
                <div className="form-group">
                  <label className="form-label">ICE — optionnel</label>
                  <input
                    className="form-control"
                    value={fields.ice}
                    onChange={e => setField('ice', e.target.value)}
                    placeholder="ex : 003799642000067"
                  />
                </div>
                <div className="form-row">
                  <div className="form-group fg-grow">
                    <label className="form-label">IF (Identifiant Fiscal) — optionnel</label>
                    <input
                      className="form-control"
                      value={fields.if_fiscal}
                      onChange={e => setField('if_fiscal', e.target.value)}
                      placeholder="ex : 12345678"
                    />
                  </div>
                  <div className="form-group fg-grow">
                    <label className="form-label">RC (Registre de Commerce) — optionnel</label>
                    <input
                      className="form-control"
                      value={fields.rc}
                      onChange={e => setField('rc', e.target.value)}
                      placeholder="N° RC"
                    />
                  </div>
                </div>
              </>
            ) : (
              <div className="form-group">
                <label className="form-label">CIN — optionnel</label>
                <input
                  className="form-control"
                  value={fields.cin}
                  onChange={e => setField('cin', e.target.value)}
                  placeholder="ex : BK123456"
                />
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Adresse</label>
              <textarea
                className="form-control"
                rows={3}
                value={fields.adresse}
                onChange={e => setField('adresse', e.target.value)}
                placeholder="Rue, ville, code postal..."
              />
            </div>

            <CustomFieldsRenderer
              module="client"
              values={customFields}
              onChange={setCustomFields}
              errors={errors.custom_fields || {}}
            />

            {errors.submit && (
              <div className="form-error-box">{errors.submit}</div>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Enregistrement...' : (isEdit ? 'Mettre à jour' : 'Créer le client')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
