import { useMemo, useState } from 'react'
import entitesApi from './entitesApi'
import {
  Button, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
  Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../ui'
import { toastError, toastSuccess } from '../../lib/toast'

/* ============================================================================
   NTADM30 — Assistant guidé « Ajouter une entité » : 3 étapes (infos de base →
   rattachement parent optionnel avec aperçu → confirmation). Validation
   anti-cycle côté serveur (400) ; ici on empêche seulement de choisir un parent
   descendant évident (le serveur reste l'arbitre).
   ========================================================================== */

export default function AssistantEntite({ open, onOpenChange, entites = [], onCreated }) {
  const [step, setStep] = useState(1)
  const [nom, setNom] = useState('')
  const [code, setCode] = useState('')
  const [parent, setParent] = useState('')
  const [saving, setSaving] = useState(false)

  const parentOptions = useMemo(() => entites.filter((e) => e.actif !== false), [entites])

  const reset = () => {
    setStep(1)
    setNom('')
    setCode('')
    setParent('')
  }

  const handleClose = (v) => {
    if (!v) reset()
    onOpenChange(v)
  }

  const submit = async () => {
    setSaving(true)
    try {
      await entitesApi.create({
        nom,
        code,
        parent: parent ? Number(parent) : null,
      })
      toastSuccess('Entité créée.')
      reset()
      onCreated?.()
    } catch (err) {
      const msg = err?.response?.data?.parent?.[0]
        || err?.response?.data?.detail
        || 'Création impossible (code déjà utilisé ou boucle de hiérarchie ?).'
      toastError(msg)
    } finally {
      setSaving(false)
    }
  }

  const parentNom = parentOptions.find((e) => String(e.id) === parent)?.nom

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ajouter une entité — étape {step}/3</DialogTitle>
        </DialogHeader>

        {step === 1 && (
          <div className="space-y-3">
            <div>
              <Label htmlFor="ent-nom">Nom</Label>
              <Input id="ent-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="ent-code">Code (unique)</Label>
              <Input id="ent-code" value={code} onChange={(e) => setCode(e.target.value)} />
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <Label>Rattachement (parent)</Label>
            <Select value={parent} onValueChange={setParent}>
              <SelectTrigger>
                <SelectValue placeholder="Aucun (racine)" />
              </SelectTrigger>
              <SelectContent>
                {parentOptions.map((e) => (
                  <SelectItem key={e.id} value={String(e.id)}>
                    {e.code} — {e.nom}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              Aperçu : {parentNom ? `${parentNom} → ${nom || '(nouvelle entité)'}` : `${nom || '(nouvelle entité)'} (racine)`}
            </p>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-2 text-sm">
            <p><strong>Nom :</strong> {nom}</p>
            <p><strong>Code :</strong> {code}</p>
            <p><strong>Parent :</strong> {parentNom || 'Aucun (racine)'}</p>
          </div>
        )}

        <DialogFooter>
          {step > 1 && (
            <Button variant="ghost" onClick={() => setStep(step - 1)} disabled={saving}>
              Précédent
            </Button>
          )}
          {step < 3 ? (
            <Button
              onClick={() => setStep(step + 1)}
              disabled={step === 1 && (!nom || !code)}
            >
              Suivant
            </Button>
          ) : (
            <Button onClick={submit} disabled={saving}>
              Créer
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
