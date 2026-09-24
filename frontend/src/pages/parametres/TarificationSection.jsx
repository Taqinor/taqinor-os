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
//
// CALX72 — les réglages SAISIS du lot 5 (tranches horaires par saison et leurs
// tarifs, mécanisme de compensation, structure de tarif, taxes et charge
// minimale, indexation, fiscalité et amortissement) ont chacun leur bloc.
// AUCUNE valeur n'y est préremplie : un champ vide reste vide, et chaque bloc
// porte ses champs source/date. Un refus (avant envoi ou 400 du serveur, clé =
// nom du champ) s'affiche SOUS le champ fautif, et un bandeau le nomme.
import { useEffect, useState } from 'react'
import { Save, CheckCircle2, Plus, Trash2 } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import {
  Card, CardContent, Input, Button, IconButton, Spinner, Switch,
} from '../../ui'
import { SectionTitle } from './peComponents'
import { toast } from '../../ui/confirm'
// VX233 — feed d'audit extrait, verrouillé sur la section « tarification ».
import SettingsAuditFeed from './SettingsAuditFeed'

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
  // VX233 — historique de la tarification, révélé à la demande.
  const [showHistory, setShowHistory] = useState(false)
  // CALX72 — réglages du lot 5 (null = non chargés : ils ne sont alors
  // jamais renvoyés, pour ne rien écraser côté serveur) + refus par champ.
  const [lot5, setLot5] = useState(null)
  const [erreurs, setErreurs] = useState({})

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
        setLot5(lot5DepuisServeur(d))
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

  // CALX72 — éditer un réglage du lot 5 efface le refus affiché sous lui.
  const oublierErreur = (champ) => setErreurs(e => {
    if (!(champ in e)) return e
    const reste = { ...e }
    delete reste[champ]
    return reste
  })
  const setL5 = (champ, valeur) => {
    setLot5(l => ({ ...l, [champ]: valeur }))
    oublierErreur(champ)
  }
  const setCellule = (saison, heure, valeur) => {
    setLot5(l => ({
      ...l,
      tou_grilles: {
        ...l.tou_grilles,
        [saison]: l.tou_grilles[saison].map((c, h) => (h === heure ? valeur : c)),
      },
    }))
    oublierErreur('tou_heures')
  }
  const setTarifTranche = (tranche, valeur) => {
    setLot5(l => ({ ...l, tou_tarifs: { ...l.tou_tarifs, [tranche]: valeur } }))
    oublierErreur('tou_tarifs')
  }
  const setTaxe = (i, cle, valeur) => {
    setLot5(l => ({
      ...l, taxes: l.taxes.map((t, j) => (j === i ? { ...t, [cle]: valeur } : t)),
    }))
    oublierErreur('taxes')
  }
  const addTaxe = () => setLot5(l => ({
    ...l, taxes: [...l.taxes, { libelle: '', taux_pct: '', assiette: '', source: '' }],
  }))
  const removeTaxe = (i) => {
    setLot5(l => ({ ...l, taxes: l.taxes.filter((_, j) => j !== i) }))
    oublierErreur('taxes')
  }
  const allerAuChamp = (champ) => {
    const cible = document.getElementById(`tarif-${champ}`)
    cible?.scrollIntoView?.({ block: 'center' })
    cible?.focus?.()
  }

  const save = async () => {
    if (!form) return
    // CALX72 — refus AVANT envoi : une valeur sourcée sans sa source n'est
    // jamais envoyée (le serveur reste l'arbitre de tout le reste).
    const refus = lot5 ? erreursAvantEnvoi(lot5) : {}
    if (Object.keys(refus).length) {
      setErreurs(refus)
      toast.error(`Non enregistré : ${Object.keys(refus).length} champ(s) à corriger.`)
      return
    }
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
        ...(lot5 ? payloadLot5(lot5) : {}),
        tolerance_kwh: Number(form.tolerance_kwh) || 0,
        selective_threshold_kwh: Number(form.selective_threshold_kwh) || 150,
        inclinaison_defaut_deg: Number(form.inclinaison_defaut_deg) || 0,
        azimut_defaut_deg: Number(form.azimut_defaut_deg) || 0,
        residential_tiers: cleanedTiers.length ? cleanedTiers : null,
      }
      const res = await parametresApi.updateTariffSettings(payload)
      setVersion(res.data?.version || version)
      if (lot5 && res.data) setLot5(lot5DepuisServeur(res.data))
      setErreurs({})
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      // CALX72 — un 400 {champ: [message]} atterrit SOUS le champ nommé.
      const parChamp = e?.response?.status === 400
        ? erreursDuServeur(e.response.data) : {}
      if (Object.keys(parChamp).length) {
        setErreurs(parChamp)
        toast.error(`Non enregistré : ${Object.keys(parChamp).length} champ(s) à corriger.`)
      } else {
        toast.error(e?.response?.data?.detail
          ?? JSON.stringify(e?.response?.data ?? 'Enregistrement impossible.'))
      }
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
            le palier supérieur ouvert. Défaut = barème ONEE 2026 (TVA 20 %) —
            change chaque année où la TVA change, réglable ici.
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

      {lot5 ? (
        <ReglagesLot5 lot5={lot5} erreurs={erreurs} setL5={setL5}
          setCellule={setCellule} setTarifTranche={setTarifTranche}
          setTaxe={setTaxe} addTaxe={addTaxe} removeTaxe={removeTaxe} />
      ) : (
        <p className="text-[12px] text-muted-foreground">
          Les réglages horaires, de compensation, de structure, de taxes,
          d’indexation et de fiscalité n’ont pas pu être chargés : ils ne seront
          pas modifiés par cet enregistrement.
        </p>
      )}

      {Object.keys(erreurs).length > 0 && (
        <div role="alert" data-testid="tarif-erreurs"
          className="rounded-xl border border-destructive/40 bg-destructive/5 px-4 py-3 text-[12.5px] text-destructive">
          <p className="font-medium">
            Non enregistré — {Object.keys(erreurs).length} champ(s) à corriger :
          </p>
          <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
            {Object.keys(erreurs).map(champ => (
              <li key={champ}>
                <button type="button" className="underline underline-offset-2"
                  onClick={() => allerAuChamp(champ)}>
                  {LIBELLES_CHAMPS[champ] || champ}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Button type="button" size="sm" onClick={save} loading={saving}
        disabled={saving} variant={saved ? 'success' : 'default'}>
        {saved
          ? <><CheckCircle2 className="size-4" aria-hidden="true" /> Enregistré !</>
          : <><Save className="size-4" aria-hidden="true" /> Enregistrer</>}
      </Button>

      {/* VX233 — historique des changements de la TARIFICATION (section
          « tarification » seule) : qui a changé le barème/ROI, quand,
          ancien→nouveau. Révélé à la demande. */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <SectionTitle label="Historique de la tarification"
              icon={<><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>} />
            <Button type="button" size="sm" variant="ghost"
              aria-expanded={showHistory}
              onClick={() => setShowHistory(v => !v)}>
              {showHistory ? 'Masquer l’historique' : 'Voir l’historique'}
            </Button>
          </div>
          {showHistory && <SettingsAuditFeed section="tarification" />}
        </CardContent>
      </Card>
    </>
  )
}

// Miroir des défauts ONEE TTC côté serveur (DEFAULT_RESIDENTIAL_TIERS).
// ORDRE FONDATEUR (19/08/2026) — TVA 20 % depuis le 01/01/2026 : valeurs 2026
// (HT × 1,20, voir apps/ventes/quote_engine/pricing.py ONEE_TRANCHES pour la
// dérivation). Affichés quand rien n'est encore enregistré ; enregistrer =
// mêmes valeurs.
// DÉCISION FONDATEUR D5 (29/08/2026) : la tranche 311-510 vaut 1,381704 —
// PROUVÉE par la facture SRM du 08/05/2026 (1,15142 HT × 1,20), et non
// l'extrapolation « HT constant ». Ce tableau doit rester le miroir EXACT de
// DEFAULT_RESIDENTIAL_TIERS (models_tariff.py) : un écart ici afficherait à la
// société un barème que le serveur n'applique pas.
const DEFAULT_TIERS = [
  { max_kwh: '100', prix_kwh_ttc: '0.916272' },
  { max_kwh: '150', prix_kwh_ttc: '1.091388' },
  { max_kwh: '210', prix_kwh_ttc: '1.091388' },
  { max_kwh: '310', prix_kwh_ttc: '1.187388' },
  { max_kwh: '510', prix_kwh_ttc: '1.381704' },
  { max_kwh: '', prix_kwh_ttc: '1.622856' },
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

// ═══════════════════════════════════════════════════════════════════════════
// CALX72 — les réglages SAISIS du lot 5 (CALX274 → CALX284)
// ═══════════════════════════════════════════════════════════════════════════
// Chaque champ porte l'id `tarif-<nom du champ serveur>` : le bandeau des
// refus y mène, et le test vérifie que chaque champ SERVI par
// `serializers_tariff.CHAMPS_LOT5` a sa porte de saisie à l'écran.

// source-choix: parametres.TariffSettings.mecanisme_compensation
const MECANISMES = [
  { value: 'injection_totale', label: 'Injection totale (toute la production vendue)' },
  { value: 'surplus', label: 'Surplus (autoconsommation + vente du surplus)' },
  { value: 'net_metering_report', label: 'Net-metering avec report de crédit' },
]

// source-choix: parametres.TariffSettings.structure_tarif
const STRUCTURES = [
  { value: 'tranches', label: 'Tranches de consommation (barème à paliers)' },
  { value: 'prix_unique', label: 'Prix unique du kWh' },
  { value: 'deux_postes', label: 'Deux postes horaires (heures hautes / basses)' },
]

// source-choix: parametres.TariffSettings.amortissement_mode
const MODES_AMORTISSEMENT = [
  { value: 'aucun', label: 'Aucun amortissement' },
  { value: 'lineaire', label: 'Linéaire' },
  { value: 'degressif', label: 'Dégressif' },
]

// source-choix: parametres.tariff.ASSIETTES_TAXE
const ASSIETTES = [
  { value: 'energie', label: 'Énergie facturée' },
  { value: 'total', label: 'Total hors taxes' },
]

// source-choix: parametres.tariff.SAISONS_TOU
const SAISONS = [
  { value: 'annuel', label: 'Toute l’année' },
  { value: 'hiver', label: 'Hiver (déc. – févr.)' },
  { value: 'printemps', label: 'Printemps (mars – mai)' },
  { value: 'ete', label: 'Été (juin – août)' },
  { value: 'automne', label: 'Automne (sept. – nov.)' },
]

const LIBELLES_CHAMPS = {
  residential_tiers: 'Barème résidentiel',
  tou_heures: 'Tranche de chaque heure',
  tou_tarifs: 'Tarif de chaque tranche',
  tou_source: 'Source des tarifs horaires',
  tou_date_source: 'Date de la source des tarifs horaires',
  mecanisme_compensation: 'Mécanisme de compensation',
  report_periode: 'Période de report du crédit',
  plafond_annuel_kwh: 'Plafond annuel compensé',
  ratio_compensation: 'Ratio de compensation',
  structure_tarif: 'Structure du tarif',
  pays_tarif: 'Pays du tarif',
  prix_unique_kwh: 'Prix unique du kWh',
  poste_haut: 'Prix en heures hautes',
  poste_bas: 'Prix en heures basses',
  prix_incluent_taxes: 'Prix taxes incluses',
  taxes: 'Taxes de la facture',
  charge_minimale_mad_jour: 'Charge minimale par jour',
  indexation_tarif_pct_an: 'Indexation annuelle du tarif',
  indexation_source: 'Source de l’indexation',
  taux_imposition_pct: 'Taux d’imposition',
  amortissement_mode: 'Mode d’amortissement',
  amortissement_duree_ans: 'Durée d’amortissement',
  amortissement_coefficient: 'Coefficient dégressif',
  fiscalite_source: 'Source de la fiscalité',
}

const HEURES = Array.from({ length: 24 }, (_, h) => h)
const grilleVide = () => HEURES.map(() => '')
const hh = (h) => `${String(h).padStart(2, '0')} h`
const texte = (v) => (v == null ? '' : String(v))
const libelleTranche = (v) => texte(v).trim().toLowerCase()
const rempli = (v) => texte(v).trim() !== ''
const nombreOuNull = (v) => (rempli(v) ? texte(v).trim() : null)

const selectCls =
  'h-[var(--control-h)] w-full rounded-md border border-input bg-card '
  + 'px-[var(--control-px)] text-base text-foreground shadow-ui-xs sm:text-sm '
  + 'transition-colors focus-visible:border-ring focus-visible:outline-none '
  + 'focus-visible:ring-2 focus-visible:ring-ring '
  + 'aria-[invalid=true]:border-destructive'

/** L'état d'édition du lot 5 tel que le serveur l'a servi — rien d'inventé. */
function lot5DepuisServeur(d) {
  const grilles = Object.fromEntries(SAISONS.map(s => [s.value, grilleVide()]))
  let parSaison = false
  if (Array.isArray(d.tou_heures)) {
    grilles.annuel = HEURES.map(h => texte(d.tou_heures[h]))
  } else if (d.tou_heures && typeof d.tou_heures === 'object') {
    parSaison = true
    for (const [saison, liste] of Object.entries(d.tou_heures)) {
      if (Array.isArray(liste) && grilles[saison]) {
        grilles[saison] = HEURES.map(h => texte(liste[h]))
      }
    }
  }
  const tarifs = {}
  if (d.tou_tarifs && typeof d.tou_tarifs === 'object') {
    for (const [tranche, prix] of Object.entries(d.tou_tarifs)) {
      tarifs[libelleTranche(tranche)] = texte(prix)
    }
  }
  const champs = [
    'tou_source', 'tou_date_source', 'mecanisme_compensation', 'report_periode',
    'plafond_annuel_kwh', 'ratio_compensation', 'structure_tarif', 'pays_tarif',
    'prix_unique_kwh', 'poste_haut', 'poste_bas', 'charge_minimale_mad_jour',
    'indexation_tarif_pct_an', 'indexation_source', 'taux_imposition_pct',
    'amortissement_mode', 'amortissement_duree_ans', 'amortissement_coefficient',
    'fiscalite_source',
  ]
  return {
    ...Object.fromEntries(champs.map(c => [c, texte(d[c])])),
    tou_par_saison: parSaison,
    tou_grilles: grilles,
    tou_tarifs: tarifs,
    // Déclaration servie telle quelle ; absente = jamais renvoyée.
    prix_incluent_taxes: typeof d.prix_incluent_taxes === 'boolean'
      ? d.prix_incluent_taxes : null,
    taxes: Array.isArray(d.taxes)
      ? d.taxes.map(t => ({
        libelle: texte(t?.libelle), taux_pct: texte(t?.taux_pct),
        assiette: texte(t?.assiette), source: texte(t?.source),
      }))
      : [],
  }
}

const saisonsEnUsage = (l) => (l.tou_par_saison ? SAISONS : SAISONS.slice(0, 1))

/** Les tranches nommées dans la (les) grille(s) affichée(s), sans doublon. */
function tranchesNommees(l) {
  const vues = []
  for (const { value } of saisonsEnUsage(l)) {
    for (const cellule of l.tou_grilles[value]) {
      const tranche = libelleTranche(cellule)
      if (tranche && !vues.includes(tranche)) vues.push(tranche)
    }
  }
  return vues
}

/** Les champs du lot 5 envoyés au serveur (vide → null, jamais un défaut). */
function payloadLot5(l) {
  let heures = null
  if (l.tou_par_saison) {
    const parSaison = {}
    for (const { value } of SAISONS) {
      const grille = l.tou_grilles[value]
      if (grille.some(rempli)) parSaison[value] = grille.map(c => c.trim())
    }
    heures = Object.keys(parSaison).length ? parSaison : null
  } else if (l.tou_grilles.annuel.some(rempli)) {
    heures = l.tou_grilles.annuel.map(c => c.trim())
  }
  const tarifs = {}
  for (const tranche of tranchesNommees(l)) {
    if (rempli(l.tou_tarifs[tranche])) tarifs[tranche] = texte(l.tou_tarifs[tranche]).trim()
  }
  const payload = {
    tou_heures: heures,
    tou_tarifs: Object.keys(tarifs).length ? tarifs : null,
    tou_source: l.tou_source.trim(),
    tou_date_source: nombreOuNull(l.tou_date_source),
    mecanisme_compensation: l.mecanisme_compensation,
    report_periode: nombreOuNull(l.report_periode),
    plafond_annuel_kwh: nombreOuNull(l.plafond_annuel_kwh),
    ratio_compensation: nombreOuNull(l.ratio_compensation),
    // Normaliser plutôt que refuser : « ma » → « MA ».
    pays_tarif: l.pays_tarif.trim().toUpperCase(),
    prix_unique_kwh: nombreOuNull(l.prix_unique_kwh),
    poste_haut: nombreOuNull(l.poste_haut),
    poste_bas: nombreOuNull(l.poste_bas),
    taxes: l.taxes.length
      ? l.taxes.map(t => ({
        libelle: t.libelle.trim(), taux_pct: t.taux_pct.trim(),
        assiette: t.assiette, source: t.source.trim(),
      }))
      : null,
    charge_minimale_mad_jour: nombreOuNull(l.charge_minimale_mad_jour),
    indexation_tarif_pct_an: nombreOuNull(l.indexation_tarif_pct_an),
    indexation_source: l.indexation_source.trim(),
    taux_imposition_pct: nombreOuNull(l.taux_imposition_pct),
    amortissement_duree_ans: nombreOuNull(l.amortissement_duree_ans),
    amortissement_coefficient: nombreOuNull(l.amortissement_coefficient),
    fiscalite_source: l.fiscalite_source.trim(),
  }
  // Deux choix sans « vide » côté serveur : envoyés seulement s'ils sont servis.
  if (l.structure_tarif) payload.structure_tarif = l.structure_tarif
  if (l.amortissement_mode) payload.amortissement_mode = l.amortissement_mode
  if (typeof l.prix_incluent_taxes === 'boolean') {
    payload.prix_incluent_taxes = l.prix_incluent_taxes
  }
  return payload
}

/** Refus AVANT envoi : une valeur sourcée saisie sans sa source (ou sa date). */
function erreursAvantEnvoi(l) {
  const refus = {}
  const touSaisi = saisonsEnUsage(l).some(({ value }) => l.tou_grilles[value].some(rempli))
    || tranchesNommees(l).some(t => rempli(l.tou_tarifs[t]))
  if (touSaisi && !rempli(l.tou_source)) {
    refus.tou_source = 'tou_source : la source des tarifs horaires est obligatoire '
      + '(facture, contrat ou barème officiel d’où viennent ces valeurs).'
  }
  if (touSaisi && !rempli(l.tou_date_source)) {
    refus.tou_date_source = 'tou_date_source : la date de la source des tarifs '
      + 'horaires est obligatoire.'
  }
  if (rempli(l.indexation_tarif_pct_an) && !rempli(l.indexation_source)) {
    refus.indexation_source = 'indexation_source : la source de l’indexation '
      + 'annuelle est obligatoire (historique des tarifs publiés, contrat, étude).'
  }
  const amorti = l.amortissement_mode === 'lineaire' || l.amortissement_mode === 'degressif'
  if ((rempli(l.taux_imposition_pct) || amorti) && !rempli(l.fiscalite_source)) {
    refus.fiscalite_source = 'fiscalite_source : la source du taux d’imposition '
      + 'et de l’amortissement est obligatoire (texte de loi, avis fiscal).'
  }
  return refus
}

/** 400 DRF `{champ: [message]}` → `{champ: message}` (clé = nom du champ). */
function erreursDuServeur(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return {}
  const parChamp = {}
  for (const [champ, valeur] of Object.entries(data)) {
    if (champ === 'detail') continue
    const messages = Array.isArray(valeur) ? valeur : [valeur]
    parChamp[champ] = messages
      .map(m => (typeof m === 'string' ? m : JSON.stringify(m)))
      .join(' ')
  }
  return parChamp
}

function ErreurChamp({ champ, erreurs }) {
  if (!erreurs[champ]) return null
  return (
    <span id={`tarif-${champ}-erreur`} role="alert" data-testid={`erreur-${champ}`}
      className="mt-1 block text-[11.5px] font-medium text-destructive">
      {erreurs[champ]}
    </span>
  )
}

// Champ étiqueté du lot 5 : vide tant que rien n'est saisi, erreur SOUS lui.
function ChampLot5({ champ, label, hint, suffix, erreurs, value, onChange, type = 'number', ...rest }) {
  const invalide = Boolean(erreurs[champ])
  return (
    <label className="block" htmlFor={`tarif-${champ}`}>
      <span className="mb-1 block text-[12.5px] font-medium text-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <Input id={`tarif-${champ}`} type={type}
          step={type === 'number' ? 'any' : undefined}
          value={value} invalid={invalide}
          aria-describedby={invalide ? `tarif-${champ}-erreur` : undefined}
          onChange={e => onChange(e.target.value)} {...rest} />
        {suffix && <span className="shrink-0 text-[12px] text-muted-foreground">{suffix}</span>}
      </div>
      {hint && <span className="mt-1 block text-[11px] text-muted-foreground">{hint}</span>}
      <ErreurChamp champ={champ} erreurs={erreurs} />
    </label>
  )
}

function ChoixLot5({ champ, label, hint, erreurs, value, onChange, children }) {
  const invalide = Boolean(erreurs[champ])
  return (
    <label className="block" htmlFor={`tarif-${champ}`}>
      <span className="mb-1 block text-[12.5px] font-medium text-foreground">{label}</span>
      <select id={`tarif-${champ}`} className={selectCls} value={value}
        aria-invalid={invalide || undefined}
        aria-describedby={invalide ? `tarif-${champ}-erreur` : undefined}
        onChange={e => onChange(e.target.value)}>
        {children}
      </select>
      {hint && <span className="mt-1 block text-[11px] text-muted-foreground">{hint}</span>}
      <ErreurChamp champ={champ} erreurs={erreurs} />
    </label>
  )
}

function GrilleHoraire({ saison, onChange }) {
  return (
    <fieldset className="space-y-1.5">
      <legend className="text-[12px] font-medium text-foreground">{saison.label}</legend>
      <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-8 lg:grid-cols-12">
        {HEURES.map(h => (
          <label key={h} className="block">
            <span className="block text-[10.5px] text-muted-foreground">{hh(h)}</span>
            <Input sanitize="off" value={saison.cellules[h]}
              aria-label={`Tranche ${saison.label} ${hh(h)}`}
              onChange={e => onChange(h, e.target.value)} />
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function ReglagesLot5({
  lot5, erreurs, setL5, setCellule, setTarifTranche, setTaxe, addTaxe, removeTaxe,
}) {
  const tranches = tranchesNommees(lot5)
  const champ = (nom, props) => (
    <ChampLot5 champ={nom} erreurs={erreurs} value={lot5[nom]}
      onChange={v => setL5(nom, v)} label={LIBELLES_CHAMPS[nom]} {...props} />
  )
  return (
    <>
      {/* CALX274/275 — tranches horaires (par saison) et leurs tarifs */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Tranches horaires et leurs tarifs"
            icon={<><circle cx="12" cy="12" r="10" /><path d="M12 7v5l3 2" /></>} />
          <p className="text-[11px] text-muted-foreground">
            Nommez la tranche de chaque heure telle que votre facture ou votre
            contrat la nomme : un champ de tarif apparaît pour chaque tranche
            nommée. Laissez tout vide si votre tarif n’est pas horaire — l’économie
            horaire sera alors omise, jamais estimée.
          </p>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <Switch id="tarif-tou_par_saison" checked={!!lot5.tou_par_saison}
              onCheckedChange={v => setL5('tou_par_saison', v)} />
            Découpage différent selon la saison
          </label>
          <div id="tarif-tou_heures" tabIndex={-1} className="space-y-3">
            {saisonsEnUsage(lot5).map(s => (
              <GrilleHoraire key={s.value}
                saison={{ ...s, cellules: lot5.tou_grilles[s.value] }}
                onChange={(h, v) => setCellule(s.value, h, v)} />
            ))}
          </div>
          <ErreurChamp champ="tou_heures" erreurs={erreurs} />
          <div id="tarif-tou_tarifs" tabIndex={-1} className="space-y-1.5">
            <span className="block text-[12.5px] font-medium text-foreground">
              {LIBELLES_CHAMPS.tou_tarifs}
            </span>
            {tranches.length === 0 ? (
              <p className="text-[11px] text-muted-foreground">
                Aucune tranche nommée dans le découpage horaire.
              </p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-3">
                {tranches.map(t => (
                  <ChampLot5 key={t} champ={`tou_tarifs-${t}`} erreurs={erreurs}
                    label={`« ${t} »`} suffix="MAD/kWh"
                    aria-label={`Tarif de la tranche ${t}`}
                    value={texte(lot5.tou_tarifs[t])}
                    onChange={v => setTarifTranche(t, v)} />
                ))}
              </div>
            )}
          </div>
          <ErreurChamp champ="tou_tarifs" erreurs={erreurs} />
          <div className="grid gap-3 sm:grid-cols-2">
            {champ('tou_source', {
              type: 'text',
              hint: 'Facture, contrat ou barème officiel d’où viennent ces valeurs.',
            })}
            {champ('tou_date_source', { type: 'date' })}
          </div>
        </CardContent>
      </Card>

      {/* CALX276 — mécanisme de compensation du surplus */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Mécanisme de compensation du surplus"
            icon={<><path d="M4 12h16" /><path d="m8 8-4 4 4 4" /><path d="m16 8 4 4-4 4" /></>} />
          <ChoixLot5 champ="mecanisme_compensation" erreurs={erreurs}
            label={LIBELLES_CHAMPS.mecanisme_compensation}
            value={lot5.mecanisme_compensation}
            onChange={v => setL5('mecanisme_compensation', v)}
            hint="À choisir selon votre contrat de raccordement. Le tarif de rachat est celui du bloc « Surplus injecté ».">
            <option value="">Aucun — le surplus n’est pas valorisé</option>
            {MECANISMES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </ChoixLot5>
          <div className="grid gap-3 sm:grid-cols-3">
            {champ('report_periode', { suffix: 'mois' })}
            {champ('plafond_annuel_kwh', { suffix: 'kWh/an' })}
            {champ('ratio_compensation', {
              hint: 'Entre 0 et 1 : 1 = un kWh injecté compense un kWh soutiré.',
            })}
          </div>
        </CardContent>
      </Card>

      {/* CALX277 — structure de la grille */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Structure du tarif"
            icon={<><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 21V9" /></>} />
          <div className="grid gap-3 sm:grid-cols-2">
            <ChoixLot5 champ="structure_tarif" erreurs={erreurs}
              label={LIBELLES_CHAMPS.structure_tarif} value={lot5.structure_tarif}
              onChange={v => setL5('structure_tarif', v)}
              hint="« Tranches » = le barème résidentiel ci-dessus.">
              {!lot5.structure_tarif && <option value="" disabled>—</option>}
              {STRUCTURES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </ChoixLot5>
            {champ('pays_tarif', {
              type: 'text', sanitize: 'code', maxLength: 2,
              hint: 'Code ISO à deux lettres.',
            })}
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {champ('prix_unique_kwh', { suffix: 'MAD/kWh', hint: 'Structure « prix unique ».' })}
            {champ('poste_haut', { suffix: 'MAD/kWh', hint: 'Structure « deux postes ».' })}
            {champ('poste_bas', { suffix: 'MAD/kWh', hint: 'Structure « deux postes ».' })}
          </div>
        </CardContent>
      </Card>

      {/* CALX278 — taxes et charge minimale */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Taxes et charge minimale"
            icon={<><path d="M19 5 5 19" /><circle cx="7" cy="7" r="2" /><circle cx="17" cy="17" r="2" /></>} />
          {typeof lot5.prix_incluent_taxes === 'boolean' && (
            <label className="flex items-center gap-2 text-sm text-foreground">
              <Switch id="tarif-prix_incluent_taxes" checked={lot5.prix_incluent_taxes}
                onCheckedChange={v => setL5('prix_incluent_taxes', v)} />
              Les prix saisis incluent les taxes (TTC)
            </label>
          )}
          <ErreurChamp champ="prix_incluent_taxes" erreurs={erreurs} />
          <p className="text-[11px] text-muted-foreground">
            Prix hors taxes : les taxes ci-dessous s’appliquent, chacune avec sa
            source.
          </p>
          <div id="tarif-taxes" tabIndex={-1} className="flex flex-col gap-2">
            {lot5.taxes.map((t, i) => (
              <div key={i} className="grid items-center gap-2 sm:grid-cols-[1fr_7rem_10rem_1.5fr_auto]">
                <Input sanitize="off" aria-label={`Libellé de la taxe ${i + 1}`}
                  value={t.libelle} onChange={e => setTaxe(i, 'libelle', e.target.value)} />
                <Input type="number" step="any" aria-label={`Taux de la taxe ${i + 1} (%)`}
                  value={t.taux_pct} onChange={e => setTaxe(i, 'taux_pct', e.target.value)} />
                <select className={selectCls} aria-label={`Assiette de la taxe ${i + 1}`}
                  value={t.assiette} onChange={e => setTaxe(i, 'assiette', e.target.value)}>
                  <option value="">Assiette…</option>
                  {ASSIETTES.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
                </select>
                <Input sanitize="off" aria-label={`Source de la taxe ${i + 1}`}
                  value={t.source} onChange={e => setTaxe(i, 'source', e.target.value)} />
                <IconButton size="sm" variant="ghost" label={`Supprimer la taxe ${i + 1}`}
                  onClick={() => removeTaxe(i)}>
                  <Trash2 className="size-3.5" aria-hidden="true" />
                </IconButton>
              </div>
            ))}
          </div>
          <ErreurChamp champ="taxes" erreurs={erreurs} />
          <Button type="button" size="sm" variant="outline" onClick={addTaxe}>
            <Plus className="size-4" aria-hidden="true" /> Ajouter une taxe
          </Button>
          <div className="grid gap-3 sm:grid-cols-2">
            {champ('charge_minimale_mad_jour', {
              suffix: 'MAD/jour', hint: 'Même base que les prix (TTC ou HT).',
            })}
          </div>
        </CardContent>
      </Card>

      {/* CALX279 — indexation annuelle */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Indexation annuelle du tarif"
            icon={<><path d="M3 17 9 11l4 4 8-8" /><path d="M15 7h6v6" /></>} />
          <div className="grid gap-3 sm:grid-cols-2">
            {champ('indexation_tarif_pct_an', {
              suffix: '%/an',
              hint: 'Vide = projection à tarif constant, avec la mention « aucune indexation saisie ».',
            })}
            {champ('indexation_source', {
              type: 'text', hint: 'Historique des tarifs publiés, contrat, étude.',
            })}
          </div>
        </CardContent>
      </Card>

      {/* CALX284 — fiscalité et amortissement */}
      <Card>
        <CardContent className="space-y-3 pt-4 sm:pt-5">
          <SectionTitle label="Fiscalité et amortissement"
            icon={<><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 7h8M8 11h8M8 15h5" /></>} />
          <p className="text-[11px] text-muted-foreground">
            Vide = aucun impôt porté : le flux après impôt reprend le flux avant
            impôt et ses indicateurs ne sont pas publiés.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {champ('taux_imposition_pct', { suffix: '%' })}
            <ChoixLot5 champ="amortissement_mode" erreurs={erreurs}
              label={LIBELLES_CHAMPS.amortissement_mode} value={lot5.amortissement_mode}
              onChange={v => setL5('amortissement_mode', v)}>
              {!lot5.amortissement_mode && <option value="" disabled>—</option>}
              {MODES_AMORTISSEMENT.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </ChoixLot5>
            {champ('amortissement_duree_ans', { suffix: 'ans' })}
            {champ('amortissement_coefficient', {
              hint: 'Mode dégressif : taux dégressif = coefficient ÷ durée.',
            })}
          </div>
          {champ('fiscalite_source', {
            type: 'text', hint: 'Texte de loi ou avis fiscal d’où viennent ces valeurs.',
          })}
        </CardContent>
      </Card>
    </>
  )
}
