// Onglet « Supervision » de la page Paramètres (N52).
// Règle la détection de SOUS-PERFORMANCE par société : seuil (% sous l'attendu)
// et bascule d'auto-création d'un ticket SAV. Section autonome (comme Statuts) :
// elle charge son propre réglage et s'enregistre via monitoringApi. Défauts =
// comportement d'aujourd'hui (bascule DÉSACTIVÉE : rien n'est créé tant qu'on
// ne l'active pas).
import { useEffect, useState } from 'react'
import { Save, CheckCircle2 } from 'lucide-react'
import monitoringApi from '../../api/monitoringApi'
import { Card, CardContent, Input, Label, Button, Spinner, Switch } from '../../ui'
import { SectionTitle } from './peComponents'

export default function MonitoringSection() {
  const [settings, setSettings] = useState(null) // null = chargement
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    monitoringApi.getSettings()
      .then((r) => setSettings({
        underperf_threshold_pct: r.data?.underperf_threshold_pct ?? 20,
        auto_create_ticket: !!r.data?.auto_create_ticket,
      }))
      .catch(() => setSettings({ underperf_threshold_pct: 20, auto_create_ticket: false }))
  }, [])

  const save = () => {
    setSaving(true)
    setSaved(false)
    monitoringApi.saveSettings({
      underperf_threshold_pct: settings.underperf_threshold_pct,
      auto_create_ticket: settings.auto_create_ticket,
    })
      .then((r) => { setSettings({ ...settings, ...r.data }); setSaved(true) })
      .catch(() => {})
      .finally(() => setSaving(false))
  }

  if (settings === null) {
    return <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-4 p-5">
        <SectionTitle
          icon={<><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></>}
          label="Supervision de la production"
        />
        <p className="text-xs text-muted-foreground">
          Quand des relevés existent pour un système, sa production est comparée à
          l’attendu. Sous le seuil ci-dessous, le système est signalé en
          sous-performance. Activez l’auto-ticket pour créer automatiquement un
          ticket SAV (sans doublon par drapeau ouvert).
        </p>

        <div className="max-w-xs">
          <Label htmlFor="underperf-threshold">Seuil de sous-performance (%)</Label>
          <Input
            id="underperf-threshold"
            type="number"
            step="any"
            value={settings.underperf_threshold_pct}
            onChange={(e) => setSettings((s) => ({ ...s, underperf_threshold_pct: e.target.value }))}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Pourcentage SOUS l’attendu déclenchant le signalement (défaut 20 %).
          </p>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <Switch
            checked={settings.auto_create_ticket}
            onCheckedChange={(v) => setSettings((s) => ({ ...s, auto_create_ticket: v }))}
          />
          Créer automatiquement un ticket SAV en cas de sous-performance
        </label>

        <div className="flex items-center gap-3">
          <Button type="button" onClick={save} disabled={saving}>
            <Save /> Enregistrer
          </Button>
          {saved && (
            <span className="flex items-center gap-1 text-sm text-emerald-600">
              <CheckCircle2 size={16} /> Enregistré
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
