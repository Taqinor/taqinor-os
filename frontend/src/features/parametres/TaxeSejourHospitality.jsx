// Paramètres → Hôtellerie : taxe de séjour (WIR8).
// `services.cloturer_folio` retombe silencieusement sur Decimal('0') tant
// qu'aucune ligne `ParametresTaxeSejour` n'est configurée — cet écran est le
// SEUL chemin d'écriture hors admin Django. Section autonome (comme
// `MonitoringSection`) : elle charge son propre réglage et s'enregistre via
// `hospitalityApi`, sans dépendre du gros formulaire `ParametresEntreprise`.
import { useEffect, useState } from 'react'
import { Save, CheckCircle2, AlertCircle } from 'lucide-react'
import hospitalityApi from '../../api/hospitalityApi'
import { Card, CardContent, Input, Label, Button, Spinner, Switch } from '../../ui'

export default function TaxeSejourHospitality() {
  const [settings, setSettings] = useState(null) // null = chargement
  const [loadError, setLoadError] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')

  const load = () => hospitalityApi.getParametresTaxeSejour()
    .then((r) => {
      setSettings({
        montant_par_nuit_par_personne: r.data?.montant_par_nuit_par_personne ?? '0',
        exoneration_enfants: r.data?.exoneration_enfants ?? true,
        actif: !!r.data?.actif,
      })
      setLoadError(false)
    })
    .catch(() => setLoadError(true))

  useEffect(() => { load() }, [])

  const save = () => {
    setSaving(true)
    setSaved(false)
    setSaveError('')
    hospitalityApi.saveParametresTaxeSejour({
      montant_par_nuit_par_personne: settings.montant_par_nuit_par_personne,
      exoneration_enfants: settings.exoneration_enfants,
      actif: settings.actif,
    })
      .then((r) => { setSettings((s) => ({ ...s, ...r.data })); setSaved(true) })
      .catch(() => { setSaved(false); setSaveError('Enregistrement impossible. Réessayez.') })
      .finally(() => setSaving(false))
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-start gap-2 py-6">
        <p className="flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="size-4" aria-hidden="true" />
          Réglages de taxe de séjour indisponibles (serveur ?).
        </p>
        <Button type="button" size="sm" variant="outline" onClick={load}>Réessayer</Button>
      </div>
    )
  }

  if (settings === null) {
    return <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
  }

  return (
    <div className="mx-auto max-w-[640px] p-6">
      <div className="mb-4">
        <h2 className="font-display text-xl font-bold tracking-tight text-foreground">
          Paramètres — Hôtellerie : taxe de séjour
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Tant qu'aucun montant n'est configuré, la taxe de séjour reste à 0 sur
          chaque folio clos.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4 p-5">
          <div className="flex items-center gap-2 text-sm">
            <Switch
              checked={settings.actif}
              onCheckedChange={(v) => setSettings((s) => ({ ...s, actif: v }))}
              id="taxe-sejour-actif"
            />
            <Label htmlFor="taxe-sejour-actif">Taxe de séjour active</Label>
          </div>

          <div className="max-w-xs">
            <Label htmlFor="taxe-sejour-montant">Montant par nuit et par personne (MAD)</Label>
            <Input
              id="taxe-sejour-montant"
              type="number"
              step="any"
              value={settings.montant_par_nuit_par_personne}
              onChange={(e) => setSettings((s) => ({
                ...s, montant_par_nuit_par_personne: e.target.value,
              }))}
            />
          </div>

          <div className="flex items-center gap-2 text-sm">
            <Switch
              checked={settings.exoneration_enfants}
              onCheckedChange={(v) => setSettings((s) => ({ ...s, exoneration_enfants: v }))}
              id="taxe-sejour-exoneration-enfants"
            />
            <Label htmlFor="taxe-sejour-exoneration-enfants">Exonérer les enfants</Label>
          </div>

          <div className="flex items-center gap-3">
            <Button type="button" onClick={save} disabled={saving}>
              <Save /> Enregistrer
            </Button>
            {saved && (
              <span className="flex items-center gap-1 text-sm text-emerald-600">
                <CheckCircle2 size={16} /> Enregistré
              </span>
            )}
            {saveError && (
              <span className="flex items-center gap-1 text-sm text-destructive">
                <AlertCircle size={16} /> {saveError}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
