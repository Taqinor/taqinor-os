import { useMemo, useState } from 'react'
import { useDispatch } from 'react-redux'
import { createClient, updateClient } from '../../features/crm/store/crmSlice'
import {
  Form, FormSection, FormField, FormErrorSummary,
  Input, Textarea, Segmented, Button, useDirtyGuard,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { toast } from '../../ui/confirm'
import { canonicalPhoneMA } from '../../lib/format'
import AttachmentsPanel from '../../components/AttachmentsPanel'
import { useT } from '../../i18n'

// Avertissements NON bloquants sur les identifiants marocains. Renvoie une
// chaîne d'aide (ou null) — n'empêche JAMAIS l'enregistrement, sert juste à
// signaler une saisie probablement incomplète à l'utilisateur.
const onlyDigits = (v) => String(v ?? '').replace(/\D/g, '')
function iceWarning(ice) {
  const v = String(ice ?? '').trim()
  if (!v) return null
  return onlyDigits(v).length === 15 ? null
    : "L'ICE comporte normalement 15 chiffres — vérifiez la saisie."
}
function ifWarning(value) {
  const v = String(value ?? '').trim()
  if (!v) return null
  const d = onlyDigits(v)
  return d.length >= 6 && d.length <= 9 ? null
    : "L'IF semble incomplet — vérifiez la saisie."
}
function rcWarning(value) {
  const v = String(value ?? '').trim()
  if (!v) return null
  // Un RC contient toujours au moins un chiffre.
  return /\d/.test(v) ? null
    : 'Le RC semble incomplet — vérifiez la saisie.'
}
function cinWarning(value) {
  const v = String(value ?? '').trim()
  if (!v) return null
  // CIN marocaine : 1 à 2 lettres suivies de chiffres (ex. BK123456).
  return /^[A-Za-z]{1,2}\d{4,8}$/.test(v) ? null
    : 'Le format CIN paraît inhabituel — vérifiez la saisie.'
}

export default function ClientForm({ client = null, onClose }) {
  const dispatch = useDispatch()
  const t = useT()
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
    // N93 — langue des documents client-facing (facture / devis). FR par défaut.
    langue_document: client?.langue_document ?? 'fr',
  }), [client])

  const [fields, setFields] = useState(initial)
  const isEntreprise = fields.type_client === 'entreprise'

  // Forme marocaine normalisée du téléphone (aperçu uniquement — on stocke
  // toujours la valeur tapée). Masquée si elle est identique à la saisie.
  const phoneHint = useMemo(() => {
    const typed = fields.telephone.trim()
    if (!typed) return ''
    const canon = canonicalPhoneMA(typed)
    return canon && canon !== typed ? canon : ''
  }, [fields.telephone])

  // Avertissements NON bloquants sur les identifiants (jamais d'erreur de
  // soumission — purement informatif).
  const idWarnings = useMemo(() => ({
    ice: isEntreprise ? iceWarning(fields.ice) : null,
    if_fiscal: isEntreprise ? ifWarning(fields.if_fiscal) : null,
    rc: isEntreprise ? rcWarning(fields.rc) : null,
    cin: isEntreprise ? null : cinWarning(fields.cin),
  }), [isEntreprise, fields.ice, fields.if_fiscal, fields.rc, fields.cin])

  // Garde « modifications non enregistrées » (sortie navigateur).
  const dirty = useMemo(
    () => Object.keys(initial).some((k) => fields[k] !== initial[k]),
    [initial, fields],
  )
  useDirtyGuard(dirty)

  const setField = (k, v) => setFields((f) => {
    const next = { ...f, [k]: v }
    // À la CRÉATION uniquement : la première fois qu'un identifiant entreprise
    // (ICE / IF / RC) est renseigné, basculer le type vers « Entreprise » —
    // parité avec le défaut en édition. On NE force jamais si un choix manuel
    // a déjà été fait (type déjà « entreprise » → no-op ; un retour manuel à
    // « particulier » est respecté car ce bloc ne se déclenche que sur la
    // saisie d'un identifiant, pas sur le changement de type).
    if (
      !isEdit
      && (k === 'ice' || k === 'if_fiscal' || k === 'rc')
      && String(v ?? '').trim() !== ''
      && f.type_client !== 'entreprise'
    ) {
      next.type_client = 'entreprise'
    }
    return next
  })

  const validate = () => {
    const e = {}
    if (!fields.nom.trim()) e.nom = 'Le nom est requis'
    // L'email est OPTIONNEL (Client.email peut être vide). On ne valide le
    // format que s'il est renseigné.
    if (fields.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email)) {
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
        // Email optionnel : chaîne vide → null (cohérent avec les autres
        // champs facultatifs ; Client.email est nullable).
        email:       fields.email.trim()     || null,
        telephone:   fields.telephone.trim() || null,
        adresse:     fields.adresse.trim()   || null,
        type_client: fields.type_client,
        // On envoie le jeu pertinent ; l'autre est vidé pour rester cohérent.
        cin:       isEntreprise ? null : (fields.cin.trim() || null),
        ice:       isEntreprise ? (fields.ice.trim() || null) : null,
        if_fiscal: isEntreprise ? (fields.if_fiscal.trim() || null) : null,
        rc:        isEntreprise ? (fields.rc.trim() || null) : null,
        // N93 — langue des documents (facture / devis) pour ce client.
        langue_document: fields.langue_document,
      }
      if (isEdit) {
        await dispatch(updateClient({ id: client.id, data: payload })).unwrap()
        toast.success('Client mis à jour.')
      } else {
        await dispatch(createClient(payload)).unwrap()
        toast.success('Client créé.')
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

  // M158 — modale centrée (≥768 px) / tiroir bas (<768 px) via ResponsiveDialog,
  // afin que l'édition d'un client soit confortable sur mobile.
  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose() }}
      title={isEdit ? 'Éditer le client' : 'Nouveau client'}
      className="sm:max-w-lg"
    >
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

              <FormField label="Email — optionnel" htmlFor="cf-email" error={errors.email}>
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
                {/* Aperçu de la forme normalisée (stockée telle que tapée) —
                    aide visuelle uniquement, ne modifie jamais la valeur. */}
                {phoneHint && (
                  <p className="form-hint" data-testid="cf-tel-hint">
                    Forme normalisée : {phoneHint}
                  </p>
                )}
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
                    {idWarnings.ice && (
                      <p className="mt-1 text-xs text-warning" data-testid="cf-ice-warning">
                        {idWarnings.ice}
                      </p>
                    )}
                  </FormField>
                  <FormField label="IF (Identifiant Fiscal) — optionnel" htmlFor="cf-if">
                    <Input
                      id="cf-if"
                      value={fields.if_fiscal}
                      onChange={e => setField('if_fiscal', e.target.value)}
                      placeholder="ex : 12345678"
                    />
                    {idWarnings.if_fiscal && (
                      <p className="mt-1 text-xs text-warning" data-testid="cf-if-warning">
                        {idWarnings.if_fiscal}
                      </p>
                    )}
                  </FormField>
                  <FormField label="RC (Registre de Commerce) — optionnel" htmlFor="cf-rc">
                    <Input
                      id="cf-rc"
                      value={fields.rc}
                      onChange={e => setField('rc', e.target.value)}
                      placeholder="N° RC"
                    />
                    {idWarnings.rc && (
                      <p className="mt-1 text-xs text-warning" data-testid="cf-rc-warning">
                        {idWarnings.rc}
                      </p>
                    )}
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
                  {idWarnings.cin && (
                    <p className="mt-1 text-xs text-warning" data-testid="cf-cin-warning">
                      {idWarnings.cin}
                    </p>
                  )}
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

              {/* N93 — langue des documents (facture / devis) pour ce client.
                  FR par défaut. Le RENDU arabe du PDF est un chantier de suivi
                  distinct ; ce champ ne fait que porter la préférence. */}
              <FormField
                label={t('client.langue_document.label')}
                htmlFor="cf-langue-document"
                fullWidth
              >
                <Segmented
                  value={fields.langue_document}
                  onChange={(v) => setField('langue_document', v)}
                  options={[
                    { value: 'fr', label: t('client.langue_document.fr') },
                    { value: 'ar', label: t('client.langue_document.ar') },
                  ]}
                />
                <p className="form-hint" data-testid="cf-langue-document-hint">
                  {t('client.langue_document.help')}
                </p>
              </FormField>
            </FormSection>

            {isEdit && client?.id && (
              <FormSection title="Pièces jointes">
                <div className="sm:col-span-2">
                  <AttachmentsPanel model="crm.client" id={client.id} />
                </div>
              </FormSection>
            )}

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
    </ResponsiveDialog>
  )
}
