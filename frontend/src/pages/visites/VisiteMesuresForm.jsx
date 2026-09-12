// VT6 — Formulaire de mesures par catégorie du wizard visite. RÈGLE MAISON
// ABSOLUE : le formulaire n'avale/ne rejette JAMAIS un nombre tapé
// (`noValidate` + `step="any"` sur tout input numérique — jamais de `min`/
// `max` qui bloquerait la saisie). Les erreurs sont CELLES DU SERVEUR
// (`PATCH .../mesures/` → 400 `{erreurs:{champ:message}}`), affichées SOUS le
// champ fautif — jamais une validation client qui pourrait diverger.
import { useState } from 'react'
import { enregistrerMesures } from '../../features/visites/visitesOffline'
import { Button, Card, Input, Label, Checkbox, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../../ui'
import { toast } from '../../ui/confirm'
import { MESURES_SCHEMA } from './visiteHelpers'

const toForm = (schema, valeurs) => {
  const out = {}
  for (const champ of schema) {
    const v = valeurs?.[champ.key]
    out[champ.key] = champ.type === 'bool' ? Boolean(v) : (v == null ? '' : String(v))
  }
  return out
}

const toPayload = (schema, form) => {
  const out = {}
  for (const champ of schema) {
    const v = form[champ.key]
    out[champ.key] = champ.type === 'bool' ? Boolean(v) : (v === '' ? null : v)
  }
  return out
}

export default function VisiteMesuresForm({ visiteId, categorie, libelle, valeurs, onSaved, lectureSeule }) {
  const schema = MESURES_SCHEMA[categorie] ?? []
  const [form, setForm] = useState(() => toForm(schema, valeurs))
  const [erreurs, setErreurs] = useState({})
  const [saving, setSaving] = useState(false)

  if (schema.length === 0) return null

  const setChamp = (key, v) => {
    setForm((prev) => ({ ...prev, [key]: v }))
    setErreurs((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev))
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErreurs({})
    try {
      // VTA10 — même appel, mais via le branchement offline : hors réseau
      // l'op part dans la file de module `visites` et on le DIT.
      const res = await enregistrerMesures(visiteId, categorie, toPayload(schema, form))
      if (res.queued) {
        toast.success('Mesures mises en file — elles partiront au retour du réseau.')
      } else {
        onSaved?.(res.data?.data)
        toast.success('Mesures enregistrées.')
      }
    } catch (err) {
      const data = err?.response?.data
      if (data?.erreurs) setErreurs(data.erreurs)
      else toast.error('Enregistrement des mesures impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="p-3" data-testid={`visite-mesures-${categorie}`}>
      <form noValidate onSubmit={submit} className="space-y-3">
        <p className="text-sm font-medium">Mesures — {libelle}</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {schema.map((champ) => {
            const id = `visite-mesure-${categorie}-${champ.key}`
            const erreur = erreurs[champ.key]
            if (champ.type === 'bool') {
              return (
                <label key={champ.key} htmlFor={id} className="flex min-h-11 items-center gap-2 text-sm">
                  <Checkbox
                    id={id}
                    checked={Boolean(form[champ.key])}
                    disabled={lectureSeule}
                    onCheckedChange={(c) => setChamp(champ.key, c === true)}
                  />
                  {champ.label}
                </label>
              )
            }
            if (champ.type === 'select') {
              return (
                <div key={champ.key}>
                  <Label htmlFor={id}>{champ.label}</Label>
                  <Select
                    value={form[champ.key] || undefined}
                    onValueChange={(v) => setChamp(champ.key, v)}
                    disabled={lectureSeule}
                  >
                    <SelectTrigger id={id}><SelectValue placeholder="—" /></SelectTrigger>
                    <SelectContent>
                      {champ.options.map((o) => (
                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {erreur && <p role="alert" className="mt-1 text-xs text-destructive">{erreur}</p>}
                </div>
              )
            }
            return (
              <div key={champ.key}>
                <Label htmlFor={id}>
                  {champ.label}{champ.unite ? ` (${champ.unite})` : ''}
                </Label>
                <Input
                  id={id}
                  type={champ.type === 'number' ? 'number' : 'text'}
                  step={champ.type === 'number' ? 'any' : undefined}
                  inputMode={champ.type === 'number' ? 'decimal' : undefined}
                  value={form[champ.key]}
                  disabled={lectureSeule}
                  aria-invalid={erreur ? 'true' : undefined}
                  onChange={(e) => setChamp(champ.key, e.target.value)}
                />
                {erreur && <p role="alert" className="mt-1 text-xs text-destructive">{erreur}</p>}
              </div>
            )
          })}
        </div>
        {!lectureSeule && (
          <Button type="submit" size="sm" disabled={saving}>Enregistrer les mesures</Button>
        )}
      </form>
    </Card>
  )
}
