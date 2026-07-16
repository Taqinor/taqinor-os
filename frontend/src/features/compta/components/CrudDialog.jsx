import { useEffect, useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Input, Label, Combobox, toast,
} from '../../../ui'
import { useFormSafety } from '../../../ui/useFormSafety'

/* ============================================================================
   Boîte de dialogue CRUD générique du module Comptabilité.
   ----------------------------------------------------------------------------
   Rend un formulaire simple à partir d'une description de champs, gère l'état
   local, l'enregistrement (create/update) et les erreurs serveur en clair. Les
   écrans passent la liste des champs et la fonction `onSubmit(values)`.

   fields : [{ name, label, type?, required?, options?:[{value,label}], step?,
     async?:() => Promise<{value,label}[]>, deriveFields?:(opt) => object }]

   VX229 — un champ `async` rend un `Combobox` de recherche (au lieu d'un
   `<Input>` FK « (ID) » tapé à la main) : ses options sont chargées UNE FOIS
   à l'ouverture du dialog (par enregistrement édité) et mémoïsées en state —
   jamais rechargées à chaque frappe/rendu. `deriveFields(opt)` pose en plus
   des champs LECTURE SEULE calculés depuis l'option choisie (ex. `tiers_nom`
   depuis le tiers sélectionné, `null` opt → champs dérivés effacés).
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
  // VX166/VX170 — snapshot pris à l'ouverture (pour détecter une saisie
  // perdue à la fermeture) + garde composée par la primitive commune.
  const [initialSnapshot, setInitialSnapshot] = useState({})
  // VX229 — options des champs `async`, chargées une fois par ouverture.
  const [asyncOptions, setAsyncOptions] = useState({})
  const [asyncLoading, setAsyncLoading] = useState({})

  // Réinitialise le formulaire à l'ouverture / au changement d'enregistrement.
  useEffect(() => {
    if (!open) return
    const base = {}
    for (const f of fields) base[f.name] = initial?.[f.name] ?? ''
    /* eslint-disable react-hooks/set-state-in-effect -- reset à l'ouverture */
    setInitialSnapshot(base)
    setValues(base)
    /* eslint-enable react-hooks/set-state-in-effect */
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initial])

  // VX229 — charge chaque champ `async` UNE FOIS à l'ouverture (mémoïsé en
  // state, jamais recréé pendant la frappe : le Combobox reçoit des `options`
  // statiques, pas un `onSearch` réseau).
  useEffect(() => {
    if (!open) return
    const asyncFields = fields.filter((f) => f.async)
    if (!asyncFields.length) return
    /* eslint-disable react-hooks/set-state-in-effect -- chargement à l'ouverture */
    setAsyncLoading((prev) => {
      const next = { ...prev }
      asyncFields.forEach((f) => { next[f.name] = true })
      return next
    })
    /* eslint-enable react-hooks/set-state-in-effect */
    asyncFields.forEach((f) => {
      f.async()
        .then((opts) => setAsyncOptions((prev) => ({ ...prev, [f.name]: opts || [] })))
        .catch(() => setAsyncOptions((prev) => ({ ...prev, [f.name]: [] })))
        .finally(() => setAsyncLoading((prev) => ({ ...prev, [f.name]: false })))
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initial])

  const { guardedClose } = useFormSafety(initialSnapshot, values, onClose)

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
    <Dialog open={open} onOpenChange={(o) => { if (!o) guardedClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          {fields.map((f, i) => (
            <div key={f.name} className="flex flex-col gap-1">
              <Label htmlFor={`cd-${f.name}`} required={f.required}>{f.label}</Label>
              {f.async ? (
                <Combobox
                  id={`cd-${f.name}`}
                  options={asyncOptions[f.name] || []}
                  value={values[f.name] || null}
                  onChange={(v, opt) => setValues((prev) => ({
                    ...prev,
                    [f.name]: v ?? '',
                    // VX229 — un champ `deriveFields(opt)` pose des champs
                    // dérivés en LECTURE SEULE au choix (ex. `tiers_nom`
                    // depuis le tiers sélectionné) : jamais tapés à la main,
                    // toujours synchronisés avec le référentiel choisi.
                    ...(f.deriveFields ? f.deriveFields(v ? opt : null) : {}),
                  }))}
                  disabled={asyncLoading[f.name]}
                  placeholder={asyncLoading[f.name] ? 'Chargement…' : 'Sélectionner…'}
                />
              ) : f.options ? (
                <select
                  id={`cd-${f.name}`}
                  autoFocus={i === 0}
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
                  autoFocus={i === 0}
                  step={f.type === 'number' ? (f.step || 'any') : undefined}
                  value={values[f.name] ?? ''}
                  onChange={(e) => set(f.name, e.target.value)}
                />
              )}
            </div>
          ))}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={guardedClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
