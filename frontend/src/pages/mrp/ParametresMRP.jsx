import { useEffect, useState } from 'react'
import { Factory } from 'lucide-react'
import api from '../../api/axios'
import { Button, Card, CardContent, Input, Label, Spinner, Switch } from '../../ui'
import { toast } from '../../ui/confirm'

/* ============================================================================
   NTMFG29 — Paramètres > Atelier MRP (`mrp.ParametresMRP`, singleton par
   société, `mrp/services.parametres_mrp`, lazy-create). Admin UNIQUEMENT côté
   backend (`mrp.permissions.EstAdminMRP`) — un Responsable planifie (NTMFG3)
   mais ne voit/modifie pas ces réglages ; un Technicien reçoit 403. Même
   patron que `TransportParametresPage.jsx` (NTLOG35).
   ========================================================================== */

const emptyForm = {
  horizon_mrp_jours: 30,
  stock_securite_pct_defaut: '0',
  tolerance_surcharge_poste_pct: '0',
  blocage_qc_force_motif_obligatoire: true,
  activer_kanban_production: false,
  retention_prototype_jours: 180,
}

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

export default function ParametresMRP() {
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    api.get('/mrp/parametres/')
      .then((r) => {
        if (!active) return
        setForm((f) => ({ ...f, ...(r.data ?? {}) }))
      })
      .catch(() => toast.error('Chargement des paramètres MRP impossible.'))
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    api.put('/mrp/parametres/update/', form)
      .then((r) => {
        setForm((f) => ({ ...f, ...(r.data ?? {}) }))
        toast.success('Paramètres MRP enregistrés.')
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
        <h1 className="page-title">Atelier MRP</h1>
        <div className="page-subtitle">
          Réglages du module MRP de la société — horizon de calcul des besoins, stock de sécurité, tolérance de surcharge, contrôle qualité, kanban de production.
        </div>
      </div>

      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <Factory className="size-4 text-muted-foreground" aria-hidden="true" />
              Calcul des besoins nets (MRP)
            </h2>

            <div className="max-w-xs">
              <Label htmlFor="pm-horizon">Horizon MRP (jours)</Label>
              <Input
                id="pm-horizon" type="number" step="1" noValidate
                value={form.horizon_mrp_jours}
                onChange={(e) => setField('horizon_mrp_jours', e.target.value)}
              />
            </div>

            <div className="max-w-xs">
              <Label htmlFor="pm-securite">Stock de sécurité par défaut (%)</Label>
              <Input
                id="pm-securite" type="number" step="any" noValidate
                value={form.stock_securite_pct_defaut}
                onChange={(e) => setField('stock_securite_pct_defaut', e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">Ordonnancement (NTMFG7)</h2>
            <div className="max-w-xs">
              <Label htmlFor="pm-tolerance">Tolérance de surcharge poste (%)</Label>
              <Input
                id="pm-tolerance" type="number" step="any" noValidate
                value={form.tolerance_surcharge_poste_pct}
                onChange={(e) => setField('tolerance_surcharge_poste_pct', e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">Contrôle qualité et production</h2>

            <div className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">Motif obligatoire pour forcer un contrôle qualité bloquant</p>
                <p className="text-xs text-muted-foreground">
                  Un contrôle qualité bloquant ne peut être forcé sans motif renseigné.
                </p>
              </div>
              <Switch
                id="pm-qc"
                checked={form.blocage_qc_force_motif_obligatoire}
                onCheckedChange={(v) => setField('blocage_qc_force_motif_obligatoire', v)}
                aria-label="Motif obligatoire pour forcer un contrôle qualité bloquant"
              />
            </div>

            <div className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">Kanban de production actif</p>
                <p className="text-xs text-muted-foreground">
                  Déclenche automatiquement un OF brouillon sous le seuil de réappro (NTMFG17).
                </p>
              </div>
              <Switch
                id="pm-kanban"
                checked={form.activer_kanban_production}
                onCheckedChange={(v) => setField('activer_kanban_production', v)}
                aria-label="Kanban de production actif"
              />
            </div>

            <div className="max-w-xs">
              <Label htmlFor="pm-retention">Rétention des OF prototype (jours)</Label>
              <Input
                id="pm-retention" type="number" step="1" noValidate
                value={form.retention_prototype_jours}
                onChange={(e) => setField('retention_prototype_jours', e.target.value)}
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
