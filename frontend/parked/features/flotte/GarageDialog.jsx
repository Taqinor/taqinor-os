import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'

/* ============================================================================
   XFLT26 — Formulaire garage (ICE / identifiant fiscal, e-facturation DGI).
   ----------------------------------------------------------------------------
   Champs facultatifs ; l'ICE (15 chiffres) est validé côté serveur — le
   message d'erreur backend est réaffiché tel quel.
   ========================================================================== */

export default function GarageDialog({ onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [adresse, setAdresse] = useState('')
  const [telephone, setTelephone] = useState('')
  const [ice, setIce] = useState('')
  const [identifiantFiscal, setIdentifiantFiscal] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(nom.trim())
  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(nom || adresse || telephone || ice || identifiantFiscal)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.garages.create({
        nom: nom.trim(),
        adresse,
        telephone,
        ice,
        identifiant_fiscal: identifiantFiscal,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.ice
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
          <DialogTitle>Nouveau garage</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gar-nom">Nom</Label>
            <Input id="gar-nom" autoFocus value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gar-adresse">Adresse</Label>
            <Input id="gar-adresse" value={adresse} onChange={(e) => setAdresse(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gar-telephone">Téléphone</Label>
            <Input id="gar-telephone" value={telephone} onChange={(e) => setTelephone(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="gar-ice">ICE</Label>
              <Input
                id="gar-ice"
                value={ice}
                onChange={(e) => setIce(e.target.value)}
                placeholder="15 chiffres"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="gar-if">Identifiant fiscal (IF)</Label>
              <Input
                id="gar-if"
                value={identifiantFiscal}
                onChange={(e) => setIdentifiantFiscal(e.target.value)}
              />
            </div>
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
