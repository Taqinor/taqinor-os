import { useEffect, useState } from 'react'
import { Card, CardContent, Input, Textarea, Switch, Button, toast } from '../../ui'
import innovationApi from '../../api/innovationApi'
import { SectionTitle, Field } from '../../pages/parametres/peComponents'

/* ============================================================================
   NTIDE7 — Paramètres → Avancé « Campagnes innovation ». Composant AUTONOME
   (fetch/save propres), monté comme une Card de plus dans AvanceSection.jsx —
   même patron que SettingsAuditFeed (VX233) : ne dépend pas du `form` géant
   de la page Paramètres (modèle backend séparé, apps/innovation).
   ========================================================================== */

const ROLES_FALLBACK = ['Technicien', 'Commercial', 'Directeur']

const THEMES = [
  { value: 'primary', label: 'Primaire' },
  { value: 'success', label: 'Succès' },
  { value: 'warning', label: 'Avertissement' },
  { value: 'info', label: 'Info' },
  { value: 'destructive', label: 'Destructive' },
]

export default function CampagnesInnovationSettings() {
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    innovationApi.parametres.get()
      .then((res) => setForm(res.data))
      .catch(() => toast.error('Impossible de charger les paramètres innovation.'))
  }, [])

  if (!form) return null

  const set = (patch) => setForm((f) => ({ ...f, ...patch }))

  const save = async () => {
    setSaving(true)
    try {
      const res = await innovationApi.parametres.update(form)
      setForm(res.data)
      toast.success('Paramètres innovation enregistrés.')
    } catch {
      toast.error('Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle
          label="Campagnes innovation"
          icon={<><path d="M9 18h6" /><path d="M10 22h4" /><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2Z" /></>}
        />
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Campagnes ciblées d'incitation à proposer des idées (boîte à idées
          interne). Désactivées par défaut — rien ne change tant que vous ne
          les activez pas.
        </p>
        <div className="pe-grid-2">
          <label className="sm:col-span-2 flex items-center gap-2.5 text-sm text-foreground">
            <Switch checked={!!form.campagnes_activees}
                    onCheckedChange={(v) => set({ campagnes_activees: !!v })} />
            Campagnes activées
          </label>
          <Field label="Segment par défaut" htmlFor="pe-innov-segment">
            <Input
              id="pe-innov-segment"
              list="pe-innov-segment-options"
              value={form.segment_defaut || ''}
              onChange={(e) => set({ segment_defaut: e.target.value })}
              placeholder="ex. Technicien, Commercial, Directeur…"
            />
            <datalist id="pe-innov-segment-options">
              {ROLES_FALLBACK.map((r) => <option key={r} value={r} />)}
            </datalist>
          </Field>
          <Field label="Thème couleur du CTA" htmlFor="pe-innov-theme">
            <select
              id="pe-innov-theme"
              className="h-[var(--control-h)] w-full rounded-md border border-input bg-card px-2 text-sm text-foreground"
              value={form.theme_couleur_cta || 'primary'}
              onChange={(e) => set({ theme_couleur_cta: e.target.value })}
            >
              {THEMES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </Field>
          <Field label="Message de relance" htmlFor="pe-innov-message">
            <Textarea
              id="pe-innov-message"
              rows={2}
              value={form.message_relance || ''}
              onChange={(e) => set({ message_relance: e.target.value })}
              placeholder="Nous cherchons vos idées sur…"
            />
          </Field>
        </div>
        <div className="mt-3">
          <Button type="button" onClick={save} disabled={saving}>
            Enregistrer
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
