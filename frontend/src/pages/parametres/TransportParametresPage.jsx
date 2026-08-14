import { useEffect, useState } from 'react'
import { Route } from 'lucide-react'
import api from '../../api/axios'
import { Button, Card, CardContent, Input, Label, Spinner, Switch } from '../../ui'
import { toast } from '../../ui/confirm'

/* ============================================================================
   NTLOG35 — Paramètres > Transport (`transport.ParametresTransport`,
   singleton par société, `ParametresTransport.for_company`). Les facteurs
   d'émission CO2 (NTLOG20) restent édités via l'écran dédié
   `facteurs-emission-co2/` — pas dupliqués ici (une seule source).
   ========================================================================== */

const emptyForm = {
  delai_alerte_retard_heures: 24,
  pod_obligatoire: true,
  seuil_anomalie_affretement_pct: '15.00',
}

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

export default function TransportParametresPage() {
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    api.get('/transport/parametres-transport/')
      .then((r) => {
        if (!active) return
        const data = r.data ?? {}
        setForm({
          delai_alerte_retard_heures: data.delai_alerte_retard_heures ?? 24,
          pod_obligatoire: data.pod_obligatoire ?? true,
          seuil_anomalie_affretement_pct: data.seuil_anomalie_affretement_pct ?? '15.00',
        })
      })
      .catch(() => toast.error('Chargement des paramètres transport impossible.'))
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    api.patch('/transport/parametres-transport/1/', form)
      .then((r) => {
        const data = r.data ?? {}
        setForm((f) => ({ ...f, ...data }))
        toast.success('Paramètres transport enregistrés.')
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
        <h1 className="page-title">Transport</h1>
        <div className="page-subtitle">
          Réglages du module transport de la société — seuil de retard, preuve de livraison obligatoire, anomalies d'affrètement.
        </div>
      </div>

      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <Route className="size-4 text-muted-foreground" aria-hidden="true" />
              Suivi des livraisons
            </h2>

            <div className="max-w-xs">
              <Label htmlFor="pt-delai">Seuil d'alerte retard (heures)</Label>
              <Input
                id="pt-delai" type="number" step="1" noValidate
                value={form.delai_alerte_retard_heures}
                onChange={(e) => setField('delai_alerte_retard_heures', e.target.value)}
              />
            </div>

            <div className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">Preuve de livraison (POD) obligatoire</p>
                <p className="text-xs text-muted-foreground">
                  Désactiver permet de clôturer une étape de livraison sans photo/signature pour cette société.
                </p>
              </div>
              <Switch
                id="pt-pod"
                checked={form.pod_obligatoire}
                onCheckedChange={(v) => setField('pod_obligatoire', v)}
                aria-label="Preuve de livraison obligatoire"
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">Anomalies d'affrètement (NTLOG28)</h2>
            <p className="text-xs text-muted-foreground">
              Seuil de dépassement du tarif de grille déclenchant une alerte de sur-facturation à vérifier manuellement.
            </p>
            <div className="max-w-xs">
              <Label htmlFor="pt-seuil">Seuil (%)</Label>
              <Input
                id="pt-seuil" type="number" step="any" noValidate
                value={form.seuil_anomalie_affretement_pct}
                onChange={(e) => setField('seuil_anomalie_affretement_pct', e.target.value)}
              />
            </div>
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
