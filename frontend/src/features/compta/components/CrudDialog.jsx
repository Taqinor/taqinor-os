import { useEffect, useRef, useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Input, Label, toast, confirmLeaveIfDirty,
} from '../../../ui'
import { isDirty } from '../../../ui/form-utils'

/* ============================================================================
   Boîte de dialogue CRUD générique du module Comptabilité.
   ----------------------------------------------------------------------------
   Rend un formulaire simple à partir d'une description de champs, gère l'état
   local, l'enregistrement (create/update) et les erreurs serveur en clair. Les
   écrans passent la liste des champs et la fonction `onSubmit(values)`.

   fields : [{ name, label, type?, required?, options?:[{value,label}], step? }]
   ========================================================================== */

export default function CrudDialog({
  open,
  onClose,
  title,
  fields = [],
  initial = null,
  onSubmit,
  onSaved,
}) {
  const [values, setValues] = useState({})
  const [saving, setSaving] = useState(false)
  // VX166 — snapshot pris à l'ouverture, pour détecter une saisie perdue à la
  // fermeture (Escape / clic-overlay / bouton Annuler).
  const initialSnapshotRef = useRef({})

  // Réinitialise le formulaire à l'ouverture / au changement d'enregistrement.
  useEffect(() => {
    if (!open) return
    const base = {}
    for (const f of fields) base[f.name] = initial?.[f.name] ?? ''
    initialSnapshotRef.current = base
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset à l'ouverture
    setValues(base)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initial])

  const dirty = isDirty(initialSnapshotRef.current, values)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const set = (name, v) => setValues((prev) => ({ ...prev, [name]: v }))

  const submit = async (e) => {
    e.preventDefault()
    // Élague les valeurs vides pour ne pas écraser des champs facultatifs.
    const payload = {}
    for (const [k, v] of Object.entries(values)) {
      if (v !== '' && v !== null && v !== undefined) payload[k] = v
    }
    setSaving(true)
    try {
      await onSubmit(payload)
      toast.success('Enregistré.')
      onSaved?.()
      onClose?.()
    } catch (err) {
      const detail = err?.response?.data
      const msg = typeof detail === 'string'
        ? detail
        : (detail?.detail || Object.values(detail || {})?.[0]
          || 'Enregistrement impossible — vérifiez les champs.')
      toast.error(Array.isArray(msg) ? msg[0] : String(msg))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          {fields.map((f) => (
            <div key={f.name} className="flex flex-col gap-1">
              <Label htmlFor={`cd-${f.name}`} required={f.required}>{f.label}</Label>
              {f.options ? (
                <select
                  id={`cd-${f.name}`}
                  className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
                  value={values[f.name] ?? ''}
                  onChange={(e) => set(f.name, e.target.value)}
                >
                  <option value="">—</option>
                  {f.options.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              ) : (
                <Input
                  id={`cd-${f.name}`}
                  type={f.type || 'text'}
                  step={f.type === 'number' ? (f.step || 'any') : undefined}
                  value={values[f.name] ?? ''}
                  onChange={(e) => set(f.name, e.target.value)}
                />
              )}
            </div>
          ))}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
