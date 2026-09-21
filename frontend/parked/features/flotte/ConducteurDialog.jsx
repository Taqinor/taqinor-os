import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'
import rhApi from '../../api/rhApi'
import useFlotteResource from './useFlotteResource'

/* ============================================================================
   WIR4 — Formulaire de création d'un Conducteur (aucun chemin de création
   n'existait, même pas l'admin Django).
   ----------------------------------------------------------------------------
   Sélecteur `employe_id` (rh.DossierEmploye, lecture cross-app via l'API —
   jamais un import direct des modèles `rh`) : pré-remplit nom/téléphone
   UNIQUEMENT si ces champs sont encore vides (même règle que XFLT12), sans
   jamais écraser une saisie déjà faite. Porte aussi les 4 champs XFLT27
   (carte de conducteur professionnel + formation continue NARSA).
   ========================================================================== */

export default function ConducteurDialog({ onClose, onSaved }) {
  const { data: employes } = useFlotteResource(
    (params) => rhApi.getEmployes(params), { statut: 'actif' },
  )

  const [employeId, setEmployeId] = useState('')
  const [nom, setNom] = useState('')
  const [telephone, setTelephone] = useState('')
  const [numeroPermis, setNumeroPermis] = useState('')
  const [categoriePermis, setCategoriePermis] = useState('')
  const [dateObtention, setDateObtention] = useState('')
  const [dateExpiration, setDateExpiration] = useState('')
  const [cartePro, setCartePro] = useState('')
  const [carteProExpiration, setCarteProExpiration] = useState('')
  const [narsaDate, setNarsaDate] = useState('')
  const [narsaValidite, setNarsaValidite] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const appliquerEmploye = (id) => {
    setEmployeId(id)
    const e = (employes || []).find((x) => String(x.id) === String(id))
    if (!e) return
    // Pré-remplit UNIQUEMENT les champs encore vides (miroir XFLT12).
    if (!nom) setNom([e.nom, e.prenom].filter(Boolean).join(' '))
    if (!telephone && e.telephone) setTelephone(e.telephone)
  }

  const peutEnregistrer = Boolean(nom.trim())
  const dirty = Boolean(
    employeId || nom || telephone || numeroPermis || categoriePermis
    || dateObtention || dateExpiration || cartePro || carteProExpiration
    || narsaDate || narsaValidite,
  )
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.conducteurs.create({
        employe_id: employeId ? Number(employeId) : null,
        nom: nom.trim(),
        telephone,
        numero_permis: numeroPermis,
        categorie_permis: categoriePermis,
        date_obtention: dateObtention || null,
        date_expiration: dateExpiration || null,
        carte_conducteur_pro_numero: cartePro,
        carte_conducteur_pro_expiration: carteProExpiration || null,
        formation_continue_narsa_date: narsaDate || null,
        formation_continue_narsa_validite: narsaValidite || null,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.nom
        || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau conducteur</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cond-employe">Employé RH (option.)</Label>
            <select
              id="cond-employe"
              autoFocus
              value={employeId}
              onChange={(e) => appliquerEmploye(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Conducteur externe (aucun dossier RH) —</option>
              {(employes || []).map((e) => (
                <option key={e.id} value={e.id}>{[e.nom, e.prenom].filter(Boolean).join(' ')}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cond-nom">Nom complet</Label>
              <Input id="cond-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cond-telephone">Téléphone</Label>
              <Input id="cond-telephone" value={telephone} onChange={(e) => setTelephone(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cond-numero-permis">N° permis</Label>
              <Input id="cond-numero-permis" value={numeroPermis} onChange={(e) => setNumeroPermis(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cond-categorie-permis">Catégorie(s) de permis</Label>
              <Input id="cond-categorie-permis" value={categoriePermis} onChange={(e) => setCategoriePermis(e.target.value)} placeholder="Ex. : B, CE" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cond-date-obtention">Date d’obtention</Label>
              <Input id="cond-date-obtention" type="date" value={dateObtention} onChange={(e) => setDateObtention(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cond-date-expiration">Date d’expiration</Label>
              <Input id="cond-date-expiration" type="date" value={dateExpiration} onChange={(e) => setDateExpiration(e.target.value)} />
            </div>
          </div>

          {/* XFLT27 — conformité transport lourd (> 3,5 t), tous optionnels. */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cond-carte-pro">N° carte conducteur pro.</Label>
              <Input id="cond-carte-pro" value={cartePro} onChange={(e) => setCartePro(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cond-carte-pro-exp">Expiration carte pro.</Label>
              <Input id="cond-carte-pro-exp" type="date" value={carteProExpiration} onChange={(e) => setCarteProExpiration(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cond-narsa-date">Formation continue NARSA</Label>
              <Input id="cond-narsa-date" type="date" value={narsaDate} onChange={(e) => setNarsaDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cond-narsa-validite">Validité formation NARSA</Label>
              <Input id="cond-narsa-validite" type="date" value={narsaValidite} onChange={(e) => setNarsaValidite(e.target.value)} />
            </div>
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
