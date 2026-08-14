import { useEffect, useState } from 'react'
import { Settings2 } from 'lucide-react'
import scmApi from '../../api/scmApi'
import { Button, Card, CardContent, Input, Label, Spinner, Switch } from '../../ui'
import { toast } from '../../ui/confirm'

/* ============================================================================
   NTSCM33 — Écran de réglages SCM par société (`apps.scm.models.
   ParametresSCM`, singleton, créé paresseusement). Horizon de prévision par
   défaut, niveaux de service par défaut par classe ABC (NTSCM6), seuils
   d'alerte (écart financier NTSCM15 câblé ; écart délai fournisseur/score
   fournisseur stockés pour un futur consommateur), rétention des prévisions
   (NTSCM36) et l'opt-in du cycle S&OP automatique (NTSCM22).

   ADAPTATION DE PÉRIMÈTRE (frontière cross-app, CLAUDE.md) : le plan visait
   `/parametres/scm` (`frontend/src/pages/parametres/`) — hors périmètre de
   cette lane (`apps/scm` ne possède que `frontend/src/pages/scm/` et
   `frontend/src/features/scm/`). Posé ICI, sous `/scm/parametres`, même
   patron d'adaptation que `models.ParametresSCM`/`models.ClassificationABC`.
   ========================================================================== */

const emptyForm = {
  horizon_prevision_mois_defaut: '3',
  service_level_defaut_a_pct: '95',
  service_level_defaut_b_pct: '90',
  service_level_defaut_c_pct: '85',
  seuil_ecart_delai_pct: '20',
  seuil_alerte_score_fournisseur_pts: '15',
  seuil_alerte_ecart_financier_pct: '15',
  retention_previsions_mois: '24',
}

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

export default function ScmParametresPage() {
  const [form, setForm] = useState(emptyForm)
  const [sopActif, setSopActif] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([scmApi.parametresScm(), scmApi.parametresSop()])
      .then(([r1, r2]) => {
        if (!active) return
        setForm((f) => ({ ...f, ...(r1.data ?? {}) }))
        setSopActif(!!r2.data?.sop_actif)
      })
      .catch(() => toast.error('Chargement des réglages SCM impossible.'))
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    Promise.all([
      scmApi.majParametresScm(form),
      scmApi.majParametresSop({ sop_actif: sopActif }),
    ])
      .then(([r1]) => {
        setForm((f) => ({ ...f, ...(r1.data ?? {}) }))
        toast.success('Réglages SCM enregistrés.')
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
        <h1 className="page-title">Planification supply — Réglages</h1>
        <div className="page-subtitle">
          Horizon de prévision, niveaux de service par défaut et seuils
          d&apos;alerte du module de planification supply chain.
        </div>
      </div>

      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <Settings2 className="size-4 text-muted-foreground" aria-hidden="true" />
              Prévision de demande
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="scm-horizon">Horizon de prévision par défaut (mois)</Label>
                <Input id="scm-horizon" type="number" step="any" noValidate
                       value={form.horizon_prevision_mois_defaut}
                       onChange={(e) => setField('horizon_prevision_mois_defaut', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="scm-retention">Rétention des prévisions (mois)</Label>
                <Input id="scm-retention" type="number" step="any" noValidate
                       value={form.retention_previsions_mois}
                       onChange={(e) => setField('retention_previsions_mois', e.target.value)} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">
              Niveaux de service par défaut (classification ABC)
            </h2>
            <p className="text-xs text-muted-foreground">
              Appliqués uniquement à la CRÉATION d&apos;une politique de
              stock — un niveau déjà personnalisé par l&apos;acheteur n&apos;est
              jamais écrasé par un recalcul.
            </p>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <Label htmlFor="scm-sl-a">Classe A (%)</Label>
                <Input id="scm-sl-a" type="number" step="any" noValidate
                       value={form.service_level_defaut_a_pct}
                       onChange={(e) => setField('service_level_defaut_a_pct', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="scm-sl-b">Classe B (%)</Label>
                <Input id="scm-sl-b" type="number" step="any" noValidate
                       value={form.service_level_defaut_b_pct}
                       onChange={(e) => setField('service_level_defaut_b_pct', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="scm-sl-c">Classe C (%)</Label>
                <Input id="scm-sl-c" type="number" step="any" noValidate
                       value={form.service_level_defaut_c_pct}
                       onChange={(e) => setField('service_level_defaut_c_pct', e.target.value)} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">Seuils d&apos;alerte</h2>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <Label htmlFor="scm-seuil-financier">Écart financier CA prévisionnel (%)</Label>
                <Input id="scm-seuil-financier" type="number" step="any" noValidate
                       value={form.seuil_alerte_ecart_financier_pct}
                       onChange={(e) => setField('seuil_alerte_ecart_financier_pct', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="scm-seuil-delai">Écart délai fournisseur (%)</Label>
                <Input id="scm-seuil-delai" type="number" step="any" noValidate
                       value={form.seuil_ecart_delai_pct}
                       onChange={(e) => setField('seuil_ecart_delai_pct', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="scm-seuil-score">Score fournisseur (points)</Label>
                <Input id="scm-seuil-score" type="number" step="any" noValidate
                       value={form.seuil_alerte_score_fournisseur_pts}
                       onChange={(e) => setField('seuil_alerte_score_fournisseur_pts', e.target.value)} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">Cycle S&amp;OP automatique</h2>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <Switch
                id="scm-sop-actif"
                aria-label="Activer l'ouverture automatique mensuelle du cycle S&OP"
                checked={sopActif}
                onCheckedChange={setSopActif}
              />
              Ouvrir automatiquement le cycle S&amp;OP du mois suivant (brouillon)
            </label>
            <p className="text-xs text-muted-foreground">
              Désactivé par défaut (comportement historique — aucun cycle
              créé automatiquement).
            </p>
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
