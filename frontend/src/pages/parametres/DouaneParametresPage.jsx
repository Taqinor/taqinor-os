import { useEffect, useState } from 'react'
import { Ship } from 'lucide-react'
import api from '../../api/axios'
import {
  Button, Card, CardContent, Input, Label,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Spinner, Textarea,
} from '../../ui'
import { toast } from '../../ui/confirm'

/* ============================================================================
   NTLOG36 — Paramètres > Douane (`douane.ParametresDouane`, singleton par
   société, `ParametresDouane.for_company`). Volet EXPORT seulement : le
   volet import (NTLOG10) reste BLOCKED — voir apps/douane/apps.py. Les
   réglages ci-dessous alimentent NTLOG22/23 (échéances) et NTLOG13/30
   (estimation droits/taxes, PDF transitaire) une fois débloqués ; leur
   contrat est déjà fixé.
   ========================================================================== */

const REGIMES = [
  { value: 'mise_consommation', label: 'Mise à la consommation' },
  { value: 'admission_temporaire', label: 'Admission temporaire' },
  { value: 'entrepot_douane', label: 'Entrepôt sous douane' },
  { value: 'transit', label: 'Transit' },
  { value: 'perfectionnement_actif', label: 'Perfectionnement actif' },
]

const emptyForm = {
  regime_douanier_par_defaut: 'mise_consommation',
  alerte_expiration_jours: [30, 15, 7],
  mention_estimation_droits: '',
}

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

export default function DouaneParametresPage() {
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    api.get('/douane/parametres-douane/')
      .then((r) => {
        if (!active) return
        const data = r.data ?? {}
        setForm({
          regime_douanier_par_defaut: data.regime_douanier_par_defaut ?? 'mise_consommation',
          alerte_expiration_jours: Array.isArray(data.alerte_expiration_jours) && data.alerte_expiration_jours.length === 3
            ? data.alerte_expiration_jours
            : [30, 15, 7],
          mention_estimation_droits: data.mention_estimation_droits ?? '',
        })
      })
      .catch(() => toast.error('Chargement des paramètres douane impossible.'))
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const setAlerteJour = (index, v) => setForm((f) => {
    const jours = [...f.alerte_expiration_jours]
    jours[index] = v === '' ? '' : Number(v)
    return { ...f, alerte_expiration_jours: jours }
  })

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    api.patch('/douane/parametres-douane/1/', form)
      .then((r) => {
        const data = r.data ?? {}
        setForm((f) => ({ ...f, ...data }))
        toast.success('Paramètres douane enregistrés.')
      })
      .catch((err) => toast.error(frErr(err, "L'enregistrement a échoué.")))
      .finally(() => setSaving(false))
  }

  if (loading) {
    return (
      <div className="page">
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </p>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Douane</h1>
        <div className="page-subtitle">
          Réglages douane de la société — régime par défaut, rappels
          d'échéance et mention affichée sur les estimations.
        </div>
      </div>

      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <Ship className="size-4 text-muted-foreground" aria-hidden="true" />
              Régime par défaut
            </h2>
            <div className="max-w-sm">
              <Label htmlFor="pd-regime">Régime douanier par défaut</Label>
              <Select
                value={form.regime_douanier_par_defaut}
                onValueChange={(v) => setField('regime_douanier_par_defaut', v)}
              >
                <SelectTrigger id="pd-regime" aria-label="Régime douanier par défaut">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REGIMES.map((r) => (
                    <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">Rappels d'échéance (NTLOG22/23)</h2>
            <p className="text-xs text-muted-foreground">
              Nombre de jours avant expiration d'un engagement d'importation ou
              d'une validité de grille tarifaire — trois paliers de rappel.
            </p>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <Label htmlFor="pd-alerte-1">1er rappel (jours)</Label>
                <Input id="pd-alerte-1" type="number" step="any" noValidate
                       value={form.alerte_expiration_jours[0] ?? ''}
                       onChange={(e) => setAlerteJour(0, e.target.value)} />
              </div>
              <div>
                <Label htmlFor="pd-alerte-2">2e rappel (jours)</Label>
                <Input id="pd-alerte-2" type="number" step="any" noValidate
                       value={form.alerte_expiration_jours[1] ?? ''}
                       onChange={(e) => setAlerteJour(1, e.target.value)} />
              </div>
              <div>
                <Label htmlFor="pd-alerte-3">3e rappel (jours)</Label>
                <Input id="pd-alerte-3" type="number" step="any" noValidate
                       value={form.alerte_expiration_jours[2] ?? ''}
                       onChange={(e) => setAlerteJour(2, e.target.value)} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">
              Mention estimation droits/taxes (NTLOG13/30)
            </h2>
            <p className="text-xs text-muted-foreground">
              Libellé affiché sur l'estimation des droits/taxes et le PDF de
              synthèse transitaire — jamais présenté comme la déclaration
              officielle.
            </p>
            <Label htmlFor="pd-mention">Mention</Label>
            <Textarea id="pd-mention" rows={2}
                      value={form.mention_estimation_droits}
                      onChange={(e) => setField('mention_estimation_droits', e.target.value)} />
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" loading={saving}>
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </div>
      </form>
    </div>
  )
}
