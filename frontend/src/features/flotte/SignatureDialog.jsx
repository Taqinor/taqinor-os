import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input,
} from '../../ui'
import { useFormSafety } from '../../ui/useFormSafety'
import flotteApi from '../../api/flotteApi'

// VX170 — snapshot de référence hors composant (constant, jamais recréé).
const EMPTY = { nom: '' }

/* ============================================================================
   XFLT17 — E-signature d'un état des lieux (loi 53-05).
   ----------------------------------------------------------------------------
   Nom saisi + horodatage posé côté serveur — pas de signature graphique, comme
   le flux devis existant. 400 si déjà signé pour ce rôle (message serveur
   réaffiché tel quel).
   ========================================================================== */

export default function SignatureDialog({ etat, role, onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(nom.trim())
  // VX168/VX170 — garde de fermeture composée par la primitive commune.
  const { guardedClose } = useFormSafety(EMPTY, { nom }, onClose)

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer || !etat?.id) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.etatsDesLieux.signer(etat.id, { role, nom: nom.trim() })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.detail
        || (typeof data === 'string' ? data : 'Signature impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) guardedClose() }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>
            {role === 'conducteur' ? 'Signature du conducteur' : 'Signature du responsable'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sig-nom">Nom (e-signature)</Label>
            <Input id="sig-nom" value={nom} onChange={(e) => setNom(e.target.value)} autoFocus />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={guardedClose}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Signature…' : 'Signer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
