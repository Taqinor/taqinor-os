import { useMemo, useState } from 'react'
import { useDispatch } from 'react-redux'
import { createClient, updateClient } from '../../features/crm/store/crmSlice'
import {
  Form, FormSection, FormField, FormErrorSummary,
  Input, Textarea, Segmented, Button, useDirtyGuard,
} from '../../ui'

export default function ClientForm({ client = null, onClose }) {
  const dispatch = useDispatch()
  const isEdit = !!client

  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  const initial = useMemo(() => ({
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
  }), [client])

  const [fields, setFields] = useState(initial)
  const isEntreprise = fields.type_client === 'entreprise'

  // Garde « modifications non enregistrées » (sortie navigateur).
  const dirty = useMemo(
    () => Object.keys(initial).some((k) => fields[k] !== initial[k]),
    [initial, fields],
  )
  useDirtyGuard(dirty)

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

  const errorList = [
    errors.nom ? { field: 'cf-nom', message: errors.nom } : null,
    errors.email ? { field: 'cf-email', message: errors.email } : null,
  ].filter(Boolean)

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            {isEdit ? 'Éditer le client' : 'Nouveau client'}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <Form onSubmit={handleSubmit}>
          <div className="modal-body">
            <FormErrorSummary errors={errorList} />

            <FormSection title="Coordonnées">
              <FormField label="Nom" required htmlFor="cf-nom" error={errors.nom}>
                <Input
                  id="cf-nom"
                  value={fields.nom}
                  invalid={!!errors.nom}
                  onChange={e => setField('nom', e.target.value)}
                  placeholder="Dupont"
                  autoFocus
                />
              </FormField>

              <FormField label="Prénom" htmlFor="cf-prenom">
                <Input
                  id="cf-prenom"
                  value={fields.prenom}
                  onChange={e => setField('prenom', e.target.value)}
                  placeholder="Jean"
                />
              </FormField>

              <FormField label="Email" required htmlFor="cf-email" error={errors.email}>
                <Input
                  id="cf-email"
                  type="email"
                  value={fields.email}
                  invalid={!!errors.email}
                  onChange={e => setField('email', e.target.value)}
                  placeholder="jean.dupont@exemple.com"
                />
              </FormField>

              <FormField label="Téléphone" htmlFor="cf-tel">
                <Input
                  id="cf-tel"
                  type="tel"
                  value={fields.telephone}
                  onChange={e => setField('telephone', e.target.value)}
                  placeholder="+212 6 XX XX XX XX"
                />
              </FormField>
            </FormSection>

            <FormSection title="Type & identifiants">
              <FormField label="Type de client" htmlFor="cf-type" fullWidth>
                <Segmented
                  value={fields.type_client}
                  onChange={(v) => setField('type_client', v)}
                  options={[
                    { value: 'particulier', label: 'Particulier' },
                    { value: 'entreprise', label: 'Entreprise' },
                  ]}
                />
              </FormField>

              {/* Identifiants selon le type : CIN pour un particulier,
                  ICE / IF / RC pour une entreprise. */}
              {isEntreprise ? (
                <>
                  <FormField label="ICE — optionnel" htmlFor="cf-ice" fullWidth>
                    <Input
                      id="cf-ice"
                      value={fields.ice}
                      onChange={e => setField('ice', e.target.value)}
                      placeholder="ex : 003799642000067"
                    />
                  </FormField>
                  <FormField label="IF (Identifiant Fiscal) — optionnel" htmlFor="cf-if">
                    <Input
                      id="cf-if"
                      value={fields.if_fiscal}
                      onChange={e => setField('if_fiscal', e.target.value)}
                      placeholder="ex : 12345678"
                    />
                  </FormField>
                  <FormField label="RC (Registre de Commerce) — optionnel" htmlFor="cf-rc">
                    <Input
                      id="cf-rc"
                      value={fields.rc}
                      onChange={e => setField('rc', e.target.value)}
                      placeholder="N° RC"
                    />
                  </FormField>
                </>
              ) : (
                <FormField label="CIN — optionnel" htmlFor="cf-cin" fullWidth>
                  <Input
                    id="cf-cin"
                    value={fields.cin}
                    onChange={e => setField('cin', e.target.value)}
                    placeholder="ex : BK123456"
                  />
                </FormField>
              )}

              <FormField label="Adresse" htmlFor="cf-adresse" fullWidth>
                <Textarea
                  id="cf-adresse"
                  rows={3}
                  value={fields.adresse}
                  onChange={e => setField('adresse', e.target.value)}
                  placeholder="Rue, ville, code postal..."
                />
              </FormField>
            </FormSection>

            {errors.submit && (
              <div className="form-error-box">{errors.submit}</div>
            )}
          </div>

          <div className="modal-footer">
            <Button type="button" variant="outline" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" loading={saving} disabled={saving}>
              {saving ? 'Enregistrement...' : (isEdit ? 'Mettre à jour' : 'Créer le client')}
            </Button>
          </div>
        </Form>
      </div>
    </div>
  )
}
