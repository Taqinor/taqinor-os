// NTUX27 — Réglages UX du module par tenant : écran /parametres/ux
// (Directeur/Admin, reflète `IsAdminOrResponsableTier` côté serveur —
// backend `apps.uxviews.UxParametres` déjà complet, singleton par société).
import { useEffect, useState } from 'react'
import { Settings2 } from 'lucide-react'
import api from '../../api/axios'
import rolesApi from '../../api/rolesApi'
import {
  Button, Card, CardContent, Input, Label, MultiSelect, Spinner, Switch,
} from '../../ui'
import { toast } from '../../ui/confirm'

const emptyForm = {
  duree_hover_peek_ms: 400,
  duree_undo_toast_s: 10,
  permettre_vues_partagees_equipe: true,
  roles_autorises_definir_defaut: [],
  max_vues_par_utilisateur: 50,
  max_favoris_par_utilisateur: 30,
}

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

export default function UxParametresPage() {
  const [form, setForm] = useState(emptyForm)
  const [roleOptions, setRoleOptions] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([api.get('/uxviews/parametres/'), rolesApi.getRoles()])
      .then(([paramRes, rolesRes]) => {
        if (!active) return
        const data = paramRes.data ?? {}
        setForm({
          duree_hover_peek_ms: data.duree_hover_peek_ms ?? 400,
          duree_undo_toast_s: data.duree_undo_toast_s ?? 10,
          permettre_vues_partagees_equipe: data.permettre_vues_partagees_equipe ?? true,
          roles_autorises_definir_defaut: data.roles_autorises_definir_defaut ?? [],
          max_vues_par_utilisateur: data.max_vues_par_utilisateur ?? 50,
          max_favoris_par_utilisateur: data.max_favoris_par_utilisateur ?? 30,
        })
        const roles = Array.isArray(rolesRes.data?.results) ? rolesRes.data.results : (rolesRes.data || [])
        setRoleOptions(roles.map((r) => ({ value: r.id, label: r.nom })))
      })
      .catch(() => toast.error('Chargement des réglages UX impossible.'))
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    api.patch('/uxviews/parametres/', form)
      .then((r) => {
        const data = r.data ?? {}
        setForm((f) => ({ ...f, ...data }))
        toast.success('Réglages UX enregistrés.')
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
        <h1 className="page-title">Réglages UX</h1>
        <div className="page-subtitle">
          Réglages transverses de l'expérience power-user (vues sauvegardées,
          favoris, édition en masse) pour votre société.
        </div>
      </div>

      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <Settings2 className="size-4 text-muted-foreground" aria-hidden="true" />
              Vues sauvegardées
            </h2>

            <div className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <p className="text-sm font-medium">Autoriser les vues partagées d'équipe</p>
                <p className="text-xs text-muted-foreground">
                  Désactiver empêche tout nouveau partage à l'équipe ; les vues
                  déjà partagées restent visibles, repassées en lecture seule.
                </p>
              </div>
              <Switch
                id="ux-partage-equipe"
                checked={form.permettre_vues_partagees_equipe}
                onCheckedChange={(v) => setField('permettre_vues_partagees_equipe', v)}
                aria-label="Autoriser les vues partagées d'équipe"
              />
            </div>

            <div>
              <Label htmlFor="ux-roles-defaut">Rôles autorisés à définir une vue par défaut</Label>
              <MultiSelect
                id="ux-roles-defaut"
                options={roleOptions}
                value={form.roles_autorises_definir_defaut}
                onChange={(vals) => setField('roles_autorises_definir_defaut', vals)}
                placeholder="Tous (Directeur/Admin) si aucun rôle choisi"
              />
            </div>

            <div className="max-w-xs">
              <Label htmlFor="ux-max-vues">Nombre maximum de vues personnelles par utilisateur</Label>
              <Input
                id="ux-max-vues" type="number" step="1" noValidate
                value={form.max_vues_par_utilisateur}
                onChange={(e) => setField('max_vues_par_utilisateur', e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">Favoris</h2>
            <div className="max-w-xs">
              <Label htmlFor="ux-max-favoris">Nombre maximum de favoris par utilisateur</Label>
              <Input
                id="ux-max-favoris" type="number" step="1" noValidate
                value={form.max_favoris_par_utilisateur}
                onChange={(e) => setField('max_favoris_par_utilisateur', e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">Interactions</h2>
            <div className="max-w-xs">
              <Label htmlFor="ux-hover">Délai avant aperçu au survol (ms)</Label>
              <Input
                id="ux-hover" type="number" step="10" noValidate
                value={form.duree_hover_peek_ms}
                onChange={(e) => setField('duree_hover_peek_ms', e.target.value)}
              />
            </div>
            <div className="max-w-xs">
              <Label htmlFor="ux-undo">Durée du bandeau « annuler » (s)</Label>
              <Input
                id="ux-undo" type="number" step="1" noValidate
                value={form.duree_undo_toast_s}
                onChange={(e) => setField('duree_undo_toast_s', e.target.value)}
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
