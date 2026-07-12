import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'
import { optionsFrom, SIGNALEMENT_GRAVITES } from './flotte'

/* ============================================================================
   XFLT5 — Formulaire « Signaler un problème » (conducteur → OrdreReparation).
   ----------------------------------------------------------------------------
   Tout rôle peut créer un signalement (comme les demandes de véhicule) —
   `company` ET `auteur` posés côté serveur. La résolution (conversion en OR)
   reste réservée aux rôles écriture (bouton séparé sur la liste).
   ========================================================================== */

export default function SignalementDialog({ actifs = [], onClose, onSaved }) {
  const [actifFlotte, setActifFlotte] = useState('')
  const [description, setDescription] = useState('')
  const [gravite, setGravite] = useState('moyenne')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(actifFlotte && description.trim())
  // VX168 — garde de fermeture : dialogue de création (gravité par défaut = 'moyenne').
  const dirty = Boolean(actifFlotte || description || gravite !== 'moyenne')
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.signalements.create({
        actif_flotte: Number(actifFlotte),
        description: description.trim(),
        gravite,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.detail
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
          <DialogTitle>Signaler un problème</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sig-actif">Véhicule / engin concerné</Label>
            <select
              id="sig-actif"
              autoFocus
              value={actifFlotte}
              onChange={(e) => setActifFlotte(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {actifs.map((a) => (
                <option key={a.id} value={a.id}>{a.label || a.immatriculation || `#${a.id}`}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sig-gravite">Gravité</Label>
            <select
              id="sig-gravite"
              value={gravite}
              onChange={(e) => setGravite(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {optionsFrom(SIGNALEMENT_GRAVITES).map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sig-description">Description du problème</Label>
            <Textarea
              id="sig-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ex. : bruit anormal au freinage, voyant moteur allumé…"
              rows={4}
            />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Signaler'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
