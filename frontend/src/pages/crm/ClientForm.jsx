import { useEffect, useMemo, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { createClient, updateClient } from '../../features/crm/store/crmSlice'
import {
  Form, FormSection, FormField, FormErrorSummary,
  Input, Textarea, Segmented, Button, Switch, useDirtyGuard, confirmLeaveIfDirty,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { Combobox } from '../../ui/Combobox'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { toast } from '../../ui/confirm'
import { canonicalPhoneMA } from '../../lib/format'
import AttachmentsPanel from '../../components/AttachmentsPanel'
import crmApi from '../../api/crmApi'
import ventesApi from '../../api/ventesApi'
import {
  searchCompanies, hitsToOptions, verifierIceUrl, verifierOmpicUrl,
} from '../../features/crm/companyLookup'
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

// VX92 — « Créer un autre » : persisté par utilisateur/poste (localStorage),
// défaut OFF (comportement historique inchangé). Un salon = 10 leads/clients
// créés d'affilée ; sans ce toggle chaque création coûte un cycle
// fermer/rouvrir (~10-30 s).
const CREER_UN_AUTRE_KEY = 'taqinor.clientForm.creerUnAutre'
function lireCreerUnAutre() {
  try {
    return window.localStorage.getItem(CREER_UN_AUTRE_KEY) === '1'
  } catch {
    return false
  }
}
function ecrireCreerUnAutre(v) {
  try {
    window.localStorage.setItem(CREER_UN_AUTRE_KEY, v ? '1' : '0')
  } catch {
    // localStorage indisponible (navigation privée, quota) : no-op silencieux.
  }
}

export default function ClientForm({ client = null, onClose }) {
  const dispatch = useDispatch()
  const t = useT()
  const isEdit = !!client

  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  // VX92 — « Créer un autre » : uniquement pertinent à la création (jamais en
  // édition), persisté (localStorage), défaut OFF.
  const [creerUnAutre, setCreerUnAutre] = useState(() => !isEdit && lireCreerUnAutre())
  const nomRef = useRef(null)

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
    // XSAL9 — société mère (hiérarchie de comptes / consolidation groupe).
    parent: client?.parent ?? null,
    // XSAL1-2 — liste de prix négociée (tarif revendeur/export). Vide =
    // prix de vente standard (comportement historique inchangé).
    liste_prix: client?.liste_prix ?? null,
  }), [client])

  const [fields, setFields] = useState(initial)
  const isEntreprise = fields.type_client === 'entreprise'

  // XSAL1-2 — listes de prix actives de la société, pour le select tarif.
  const [listesPrix, setListesPrix] = useState([])
  useEffect(() => {
    ventesApi.getListesPrix().then(({ data }) => {
      setListesPrix(data.results ?? data)
    }).catch(() => {})
  }, [])

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

  // QC1 — autocomplete entreprise (données propres). Avertissement de doublon
  // non bloquant quand on choisit un CLIENT existant (au lieu de recréer).
  const [dupWarning, setDupWarning] = useState(null)

  const onSearchCompany = (query) =>
    searchCompanies(query, { searcher: crmApi.searchClients }).then(hitsToOptions)

  // Remplissage depuis un match choisi : ne remplit que les champs vides pour
  // ne jamais écraser une saisie de l'utilisateur ; bascule en entreprise si
  // le match porte un ICE.
  const fillFromHit = (hit) => {
    if (!hit) return
    setFields((f) => {
      const fillIf = (cur, val) => (String(cur ?? '').trim() ? cur : (val || cur))
      const next = {
        ...f,
        nom: hit.nom || f.nom,
        ice: fillIf(f.ice, hit.ice),
        if_fiscal: fillIf(f.if_fiscal, hit.if_fiscal),
        rc: fillIf(f.rc, hit.rc),
        adresse: fillIf(f.adresse, hit.adresse),
        telephone: fillIf(f.telephone, hit.telephone),
        email: fillIf(f.email, hit.email),
      }
      if ((hit.ice || '').trim()) next.type_client = 'entreprise'
      return next
    })
    setDupWarning(hit.source === 'client'
      ? `« ${hit.nom} » existe déjà comme client. Vérifiez avant de créer un doublon.`
      : null)
  }

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
        // XSAL9 — société mère (hiérarchie de comptes), optionnelle.
        parent: fields.parent || null,
        // XSAL1-2 — liste de prix négociée, optionnelle.
        liste_prix: fields.liste_prix || null,
      }
      if (isEdit) {
        await dispatch(updateClient({ id: client.id, data: payload })).unwrap()
        toast.success('Client mis à jour.')
        onClose()
      } else {
        await dispatch(createClient(payload)).unwrap()
        toast.success('Client créé.')
        // VX92 — « Créer un autre » : on vide le formulaire et on refocalise
        // le champ 1 au lieu de fermer le dialog.
        if (creerUnAutre) {
          setFields(initial)
          setErrors({})
          setDupWarning(null)
          nomRef.current?.focus()
        } else {
          onClose()
        }
      }
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
      onOpenChange={(o) => { if (!o && confirmLeaveIfDirty(dirty)) onClose() }}
      title={isEdit ? 'Éditer le client' : 'Nouveau client'}
      className="sm:max-w-lg"
    >
      <Form onSubmit={handleSubmit}>
        <div className="modal-body">
          <FormErrorSummary errors={errorList} />

            <FormSection title="Coordonnées">
              {/* QC1 — autocomplete entreprise (données propres). À la création
                  uniquement : taper un nom suggère les clients/fournisseurs/
                  leads existants ; choisir remplit ICE/IF/RC/adresse/téléphone
                  et avertit d'un doublon plutôt que de recréer. */}
              {!isEdit && (
                <FormField label="Rechercher une entreprise existante — optionnel"
                           htmlFor="cf-company-search" fullWidth>
                  <Combobox
                    id="cf-company-search"
                    value={null}
                    onSearch={onSearchCompany}
                    onChange={(_v, opt) => fillFromHit(opt?.hit)}
                    placeholder="Taper un nom d'entreprise…"
                    searchPlaceholder="Nom ou ICE…"
                    emptyText="Aucune correspondance dans vos données"
                    clearable={false}
                  />
                  {dupWarning && (
                    <p className="mt-1 text-xs text-warning" data-testid="cf-dup-warning">
                      {dupWarning}
                    </p>
                  )}
                </FormField>
              )}

              <FormField label="Nom" required htmlFor="cf-nom" error={errors.nom}>
                <Input
                  id="cf-nom"
                  ref={nomRef}
                  value={fields.nom}
                  invalid={!!errors.nom}
                  onChange={e => setField('nom', e.target.value)}
                  placeholder="Dupont"
                  autoFocus
                />
                {/* QC1 — « Vérifier » : deep-link registres officiels (nouvel
                    onglet), copier-coller manuel ponctuel, zéro scraping. */}
                {isEntreprise && fields.nom.trim() && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Vérifier :{' '}
                    <a href={verifierIceUrl(fields.nom)} target="_blank" rel="noreferrer"
                       className="underline hover:text-foreground">registre ICE</a>
                    {' · '}
                    <a href={verifierOmpicUrl(fields.nom)} target="_blank" rel="noreferrer"
                       className="underline hover:text-foreground">OMPIC</a>
                  </p>
                )}
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

              {/* XSAL9 — hiérarchie de comptes : société mère (optionnelle).
                  Rattache ce client à un groupe sans fusionner leurs données ;
                  anti-cycle + isolation société vérifiés côté serveur. */}
              <FormField
                label="Société mère (groupe) — optionnel"
                htmlFor="cf-parent" fullWidth
              >
                <Combobox
                  id="cf-parent"
                  value={fields.parent ? String(fields.parent) : null}
                  onSearch={onSearchCompany}
                  onChange={(_v, opt) => setField('parent', opt?.hit?.id ?? null)}
                  placeholder="Rechercher la société mère…"
                  searchPlaceholder="Nom ou ICE…"
                  emptyText="Aucune correspondance"
                />
                {fields.parent && (
                  <button
                    type="button"
                    className="form-hint"
                    style={{ cursor: 'pointer', textDecoration: 'underline' }}
                    onClick={() => setField('parent', null)}
                  >
                    Retirer le rattachement
                  </button>
                )}
              </FormField>

              {/* XSAL1-2 — tarif négocié (liste de prix). Vide = prix de vente
                  standard, résolu par apps.ventes.services.prix_applicable. */}
              <FormField
                label="Liste de prix — optionnel"
                htmlFor="cf-liste-prix" fullWidth
              >
                <Select
                  value={fields.liste_prix ? String(fields.liste_prix) : 'none'}
                  onValueChange={(v) => setField('liste_prix', v === 'none' ? null : v)}
                >
                  <SelectTrigger id="cf-liste-prix"><SelectValue placeholder="Prix de vente standard" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Prix de vente standard</SelectItem>
                    {listesPrix.map((lp) => (
                      <SelectItem key={lp.id} value={String(lp.id)}>{lp.nom}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
          {/* VX92 — « Créer un autre » : seulement à la création. */}
          {!isEdit && (
            <label className="mr-auto flex items-center gap-2 text-sm text-muted-foreground">
              <Switch
                checked={creerUnAutre}
                onCheckedChange={(v) => { setCreerUnAutre(v); ecrireCreerUnAutre(v) }}
                aria-label="Créer un autre"
              />
              Créer un autre
            </label>
          )}
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
