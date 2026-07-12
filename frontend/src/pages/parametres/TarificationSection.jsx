// Onglet « Tarification & ROI » de la page Paramètres (N64/N65).
// Édite le barème ONEE résidentiel (paliers TTC), le modèle de facturation
// (progressif ≤150 kWh / sélectif au-delà, tolérance 10 kWh), la classe « force
// motrice / agricole » (moins chère), la valorisation du surplus injecté (par
// défaut DÉSACTIVÉE — pas de net-metering au Maroc) et les hypothèses
// ROI/productible (autoconsommation, pertes, PVGIS + repli manuel conservateur).
//
// Tout est SEEDÉ sur les défauts courants côté serveur : rien n'est codé en dur
// ici, on lit/écrit les réglages versionnés. Section autonome (comme
// DocumentsSection / StatutsSection) : charge ses réglages, édite en local,
// enregistre via parametresApi.updateTariffSettings.
import { useEffect, useState } from 'react'
import { Save, CheckCircle2, Plus, Trash2 } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import {
  Card, CardContent, Input, Button, IconButton, Spinner, Switch,
} from '../../ui'
import { SectionTitle } from './peComponents'
import { toast } from '../../ui/confirm'

// Champ numérique étiqueté + indice. step="any" : la frappe reste souveraine.
function NumField({ label, value, onChange, hint, suffix }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[12.5px] font-medium text-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <Input type="number" step="any" value={value}
          onChange={e => onChange(e.target.value)} />
        {suffix && <span className="text-[12px] text-muted-foreground">{suffix}</span>}
      </div>
      {hint && (
        <span className="mt-1 block text-[11px] text-muted-foreground">{hint}</span>
      )}
    </label>
  )
}

export default function TarificationSection() {
  const [form, setForm] = useState(null) // null = chargement
  const [tiers, setTiers] = useState([])
  const [version, setVersion] = useState(1)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    parametresApi.getTariffSettings()
      .then(r => {
        const d = r.data || {}
        setForm({
          tolerance_kwh: d.tolerance_kwh ?? 10,
          selective_threshold_kwh: d.selective_threshold_kwh ?? 150,
          force_motrice_prix_kwh_ttc: d.force_motrice_prix_kwh_ttc ?? '0.9500',
          surplus_injecte_compense: !!d.surplus_injecte_compense,
          surplus_prix_kwh_ttc: d.surplus_prix_kwh_ttc ?? '0.0000',
          autoconsommation_pct_defaut: d.autoconsommation_pct_defaut ?? '70.00',
          pertes_systeme_pct: d.pertes_systeme_pct ?? '20.00',
          pvgis_actif: d.pvgis_actif ?? true,
          productible_manuel_kwh_kwc: d.productible_manuel_kwh_kwc ?? '1500.0',
          inclinaison_defaut_deg: d.inclinaison_defaut_deg ?? 30,
          azimut_defaut_deg: d.azimut_defaut_deg ?? 0,
        })
        // Paliers : on travaille sur des chaînes éditables. La liste renvoyée
        // par le serveur (ou vide) sera celle des défauts ONEE.
        setTiers(Array.isArray(d.residential_tiers) && d.residential_tiers.length
          ? d.residential_tiers.map(t => ({
            max_kwh: t.max_kwh == null ? '' : String(t.max_kwh),
            prix_kwh_ttc: String(t.prix_kwh_ttc),
          }))
          : DEFAULT_TIERS.map(t => ({ ...t })))
        setVersion(d.version || 1)
      })
      .catch(() => {
        setForm(FALLBACK_FORM)
        setTiers(DEFAULT_TIERS.map(t => ({ ...t })))
      })
  }, [])

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))
  const setTier = (i, key, val) =>
    setTiers(ts => ts.map((t, j) => (j === i ? { ...t, [key]: val } : t)))
  const addTier = () => setTiers(ts => [...ts, { max_kwh: '', prix_kwh_ttc: '' }])
  const removeTier = (i) => setTiers(ts => ts.filter((_, j) => j !== i))

  const save = async () => {
    if (!form) return
    setSaving(true)
    try {
      // Paliers : max_kwh vide → null (palier ouvert) ; prix en chaîne.
      const cleanedTiers = tiers
        .filter(t => String(t.prix_kwh_ttc).trim() !== '')
        .map(t => ({
          max_kwh: String(t.max_kwh).trim() === '' ? null : Number(t.max_kwh),
          prix_kwh_ttc: String(t.prix_kwh_ttc).trim(),
        }))
      const payload = {
        ...form,
        tolerance_kwh: Number(form.tolerance_kwh) || 0,
        selective_threshold_kwh: Number(form.selective_threshold_kwh) || 150,
        inclinaison_defaut_deg: Number(form.inclinaison_defaut_deg) || 0,
        azimut_defaut_deg: Number(form.azimut_defaut_deg) || 0,
        residential_tiers: cleanedTiers.length ? cleanedTiers : null,
      }
      const res = await parametresApi.updateTariffSettings(payload)
      setVersion(res.data?.version || version)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      toast.error(e?.response?.data?.detail
        ?? JSON.stringify(e?.response?.data ?? 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  if (form === null) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <Spinner className="size-4 text-primary" /> Chargement…
      </div>
    )
  }

  return (
    <>
      <div className="rounded-xl border border-border bg-muted/30 px-4 py-3 text-[12.5px] leading-relaxed text-muted-foreground">
        Réglez le <strong>barème ONEE</strong> et les hypothèses de
        <strong> rentabilité</strong> utilisées pour estimer les économies d’un
        projet. Les prix du barème sont déjà <strong>TTC</strong> (jamais de TVA
        ajoutée). Facturation <strong>progressive</strong> jusqu’au seuil,
        <strong> sélective</strong> au-delà (mois entier au tarif de la tranche
        atteinte). <span className="whitespace-nowrap">Révision : v{version}.</span>
      </div>

      {/* Barème ONEE résidentiel */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Barème ONEE résidentiel (TTC)"
            icon={<><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-3 3" /></>} />
          <p className="text-[11px] text-muted-foreground">
            Paliers mensuels (kWh → prix MAD/kWh TTC). Laissez la borne vide pour
            le palier supérieur ouvert. Défaut = barème ONEE 2024.
          </p>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2 text-[11px] font-medium text-muted-foreground">
              <span className="flex-1">Jusqu’à (kWh/mois)</span>
              <span className="flex-1">Prix MAD/kWh TTC</span>
              <span className="w-8" />
            </div>
            {tiers.map((t, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input className="flex-1" type="number" step="any"
                  placeholder="∞ (palier ouvert)"
                  aria-label={`Borne palier ${i + 1}`}
                  value={t.max_kwh} onChange={e => setTier(i, 'max_kwh', e.target.value)} />
                <Input className="flex-1" type="number" step="any"
                  aria-label={`Prix palier ${i + 1}`}
                  value={t.prix_kwh_ttc}
                  onChange={e => setTier(i, 'prix_kwh_ttc', e.target.value)} />
                <IconButton size="sm" variant="ghost" label="Supprimer ce palier"
                  onClick={() => removeTier(i)}>
                  <Trash2 className="size-3.5" aria-hidden="true" />
                </IconButton>
              </div>
            ))}
          </div>
          <Button type="button" size="sm" variant="outline" onClick={addTier}>
            <Plus className="size-4" aria-hidden="true" /> Ajouter un palier
          </Button>
        </CardContent>
      </Card>

      {/* Modèle de facturation */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Modèle de facturation"
            icon={<><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18" /></>} />
          <div className="grid gap-3 sm:grid-cols-2">
            <NumField label="Seuil progressif → sélectif"
              value={form.selective_threshold_kwh}
              onChange={v => set('selective_threshold_kwh', v)} suffix="kWh/mois"
              hint="≤ seuil : progressif (chaque tranche à son prix). > seuil : sélectif." />
            <NumField label="Tolérance" value={form.tolerance_kwh}
              onChange={v => set('tolerance_kwh', v)} suffix="kWh"
              hint="Décale les bornes opératoires (200/300/500 → 210/310/510)." />
          </div>
        </CardContent>
      </Card>

      {/* Force motrice / agricole */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Force motrice / agricole"
            icon={<><path d="M12 2v20" /><path d="M2 12h20" /></>} />
          <NumField label="Tarif unique force motrice / agricole"
            value={form.force_motrice_prix_kwh_ttc}
            onChange={v => set('force_motrice_prix_kwh_ttc', v)} suffix="MAD/kWh TTC"
            hint="Classe séparée, moins chère que le haut barème résidentiel (~0,90–0,95)." />
        </CardContent>
      </Card>

      {/* Surplus injecté */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Surplus injecté"
            icon={<><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></>} />
          <label className="flex items-center gap-2 text-sm text-foreground">
            <Switch checked={!!form.surplus_injecte_compense}
              onCheckedChange={v => set('surplus_injecte_compense', v)} />
            Compenser / valoriser le surplus injecté
          </label>
          <p className="text-[11px] text-muted-foreground">
            Par défaut désactivé : pas de net-metering au Maroc, le surplus vaut
            zéro et on dimensionne sur l’autoconsommation.
          </p>
          {form.surplus_injecte_compense && (
            <NumField label="Tarif de rachat du surplus"
              value={form.surplus_prix_kwh_ttc}
              onChange={v => set('surplus_prix_kwh_ttc', v)} suffix="MAD/kWh TTC" />
          )}
        </CardContent>
      </Card>

      {/* Hypothèses ROI */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Hypothèses de rentabilité"
            icon={<><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>} />
          <div className="grid gap-3 sm:grid-cols-2">
            <NumField label="Autoconsommation par défaut"
              value={form.autoconsommation_pct_defaut}
              onChange={v => set('autoconsommation_pct_defaut', v)} suffix="%"
              hint="Part de la production réellement consommée sur site (conservateur)." />
            <NumField label="Pertes système" value={form.pertes_systeme_pct}
              onChange={v => set('pertes_systeme_pct', v)} suffix="%"
              hint="Onduleur, câblage, salissure, température." />
          </div>
        </CardContent>
      </Card>

      {/* Productible / PVGIS */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Productible & irradiation (PVGIS)"
            icon={<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4 12H2M22 12h-2" /></>} />
          <label className="flex items-center gap-2 text-sm text-foreground">
            <Switch checked={!!form.pvgis_actif}
              onCheckedChange={v => set('pvgis_actif', v)} />
            Interroger PVGIS au point GPS exact du site
          </label>
          <p className="text-[11px] text-muted-foreground">
            Si PVGIS est indisponible (réseau bloqué), on retombe automatiquement
            sur le productible manuel conservateur ci-dessous.
          </p>
          <div className="grid gap-3 sm:grid-cols-3">
            <NumField label="Productible manuel (repli)"
              value={form.productible_manuel_kwh_kwc}
              onChange={v => set('productible_manuel_kwh_kwc', v)}
              suffix="kWh/kWc/an" />
            <NumField label="Inclinaison par défaut"
              value={form.inclinaison_defaut_deg}
              onChange={v => set('inclinaison_defaut_deg', v)} suffix="°" />
            <NumField label="Azimut par défaut" value={form.azimut_defaut_deg}
              onChange={v => set('azimut_defaut_deg', v)} suffix="°"
              hint="Sud 0 · Est −90 · Ouest +90 · Nord +180." />
          </div>
        </CardContent>
      </Card>

      <Button type="button" size="sm" onClick={save} loading={saving}
        disabled={saving} variant={saved ? 'success' : 'default'}>
        {saved
          ? <><CheckCircle2 className="size-4" aria-hidden="true" /> Enregistré !</>
          : <><Save className="size-4" aria-hidden="true" /> Enregistrer</>}
      </Button>
    </>
  )
}

// Miroir des défauts ONEE TTC côté serveur (DEFAULT_RESIDENTIAL_TIERS). Affichés
// quand rien n'est encore enregistré ; enregistrer = mêmes valeurs.
const DEFAULT_TIERS = [
  { max_kwh: '100', prix_kwh_ttc: '0.9010' },
  { max_kwh: '150', prix_kwh_ttc: '1.0732' },
  { max_kwh: '210', prix_kwh_ttc: '1.0732' },
  { max_kwh: '310', prix_kwh_ttc: '1.1676' },
  { max_kwh: '510', prix_kwh_ttc: '1.3817' },
  { max_kwh: '', prix_kwh_ttc: '1.5958' },
]

const FALLBACK_FORM = {
  tolerance_kwh: 10,
  selective_threshold_kwh: 150,
  force_motrice_prix_kwh_ttc: '0.9500',
  surplus_injecte_compense: false,
  surplus_prix_kwh_ttc: '0.0000',
  autoconsommation_pct_defaut: '70.00',
  pertes_systeme_pct: '20.00',
  pvgis_actif: true,
  productible_manuel_kwh_kwc: '1500.0',
  inclinaison_defaut_deg: 30,
  azimut_defaut_deg: 0,
}
