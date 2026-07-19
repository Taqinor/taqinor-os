import { useEffect, useMemo, useState } from 'react'
import { Leaf, PlusCircle } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import {
  Tabs, TabsList, TabsTrigger, TabsContent, Badge, Card,
  Dialog, DialogContent, DialogTitle, Button, Label, Input, Textarea, toast,
} from '../../ui'
import { FieldSelect } from './QhseForm'
import { BarArrondie } from '../../ui/charts'
import { formatDate, formatNumber } from '../../lib/format'
import { QhseResourceList } from './QhseResourceList'
import { rowsFrom } from './useQhseList'
import {
  BsdStatutPill, RecyclageStatutPill, ConformiteStatutPill, BilanStatutPill,
  EsgPilierPill,
} from './qhsePills'
import { num } from './qhseStatus'
import { useHasPermission } from '../../hooks/useHasPermission'

// XQHS22 — coût de la non-qualité (CoQ), gardé par `cout_non_qualite_voir`.
// Le serveur renvoie déjà les montants à `null` sans la permission (structure
// identique) : ce composant s'affiche toujours, mais montre « — » sans accès.
function CoutNonQualiteCard() {
  const canView = useHasPermission('cout_non_qualite_voir')
  const [rollup, setRollup] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    qhseApi.coutNonQualite()
      .then((res) => { if (alive) setRollup(res.data) })
      .catch(() => { if (alive) setRollup(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  if (loading || !rollup) return null

  const fmtMontant = (v) => (v == null ? '—' : `${formatNumber(v, { decimals: 0 })} MAD`)

  return (
    <Card className="p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-display text-base font-semibold tracking-tight">
          Coût de la non-qualité {rollup.annee ?? ''}
        </h3>
        {!canView && (
          <Badge tone="neutral">Montants masqués (permission requise)</Badge>
        )}
      </div>
      <div className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-muted-foreground">Interne</div>
          <div className="font-semibold tabular-nums">{fmtMontant(rollup.interne)}</div>
        </div>
        <div>
          <div className="text-muted-foreground">Externe</div>
          <div className="font-semibold tabular-nums">{fmtMontant(rollup.externe)}</div>
        </div>
        <div>
          <div className="text-muted-foreground">Total</div>
          <div className="font-semibold tabular-nums">{fmtMontant(rollup.total)}</div>
        </div>
      </div>
    </Card>
  )
}

/* ============================================================================
   UX33 — Environnement & ESG.
   ----------------------------------------------------------------------------
   Onglets :
   • Déchets : référentiel déchets + bordereaux de suivi (BSD, loi 28-00).
   • Recyclage PV : recyclage des modules photovoltaïques.
   • Conformité : conformités environnementales (autorisations, échéances).
   • Bilan carbone : bilans (scopes 1/2/3) avec graphe tCO₂e + lignes.
   • ESG : indicateurs E/S/G.
   ========================================================================== */

function BilanCarboneChart() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    qhseApi.bilansCarbone.list()
      .then((res) => { if (alive) setRows(rowsFrom(res)) })
      .catch(() => { if (alive) setRows([]) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  // Bilan le plus récent (année max) → décomposition par scope.
  const latest = useMemo(() => {
    if (!rows.length) return null
    return [...rows].sort((a, b) => (b.annee ?? 0) - (a.annee ?? 0))[0]
  }, [rows])

  if (loading || !latest) return null

  const scopes = [
    { label: 'Scope 1', value: num(latest.total_scope_1) ?? 0 },
    { label: 'Scope 2', value: num(latest.total_scope_2) ?? 0 },
    { label: 'Scope 3', value: num(latest.total_scope_3) ?? 0 },
  ]
  const total = num(latest.total_tco2e) ?? 0

  return (
    <Card className="p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-display text-base font-semibold tracking-tight">
          Bilan carbone {latest.annee ?? ''} — {latest.libelle}
        </h3>
        <Badge tone="success">
          {formatNumber(total, { decimals: 2 })} tCO₂e
        </Badge>
      </div>
      <BarArrondie
        data={scopes}
        height={200}
        tone="success"
        name="tCO₂e"
        tooltipFormat={(v) => `${formatNumber(v, { decimals: 2 })} tCO₂e`}
      />
    </Card>
  )
}

/* ============================================================================
   WIR127 — création par onglet (Environnement & ESG).
   ----------------------------------------------------------------------------
   Le backend supporte toute la création/cycle de vie, mais les 10 registres
   restaient en lecture seule. Un dialogue générique piloté par une spec de
   champs ouvre au minimum la CRÉATION sur chaque onglet — déchets/BSD et bilan
   carbone en priorité (loi 28-00). `company`/`auteur` sont posés côté serveur.
   ========================================================================== */

const CURRENT_YEAR = new Date().getFullYear()

const ENV_CREATE_SPECS = {
  dechets: {
    title: 'Nouveau déchet', create: (d) => qhseApi.dechets.create(d),
    fields: [
      { name: 'libelle', label: 'Libellé', type: 'text', required: true },
      { name: 'code', label: 'Code', type: 'text' },
      {
        name: 'categorie', label: 'Catégorie', type: 'select', default: 'non_dangereux',
        options: [
          { value: 'dangereux', label: 'Dangereux' },
          { value: 'non_dangereux', label: 'Non dangereux' },
          { value: 'inerte', label: 'Inerte' },
        ],
      },
      {
        name: 'mode_traitement', label: 'Mode de traitement', type: 'select', default: 'recyclage',
        options: [
          { value: 'recyclage', label: 'Recyclage / valorisation' },
          { value: 'enfouissement', label: 'Enfouissement' },
          { value: 'incineration', label: 'Incinération' },
          { value: 'traitement_specialise', label: 'Traitement spécialisé' },
          { value: 'autre', label: 'Autre' },
        ],
      },
      { name: 'unite', label: 'Unité', type: 'text', default: 'kg' },
    ],
  },
  bordereauxDechets: {
    title: 'Nouveau bordereau (BSD)', create: (d) => qhseApi.bordereauxDechets.create(d),
    fields: [
      {
        name: 'dechet', label: 'Déchet', type: 'loadedSelect', required: true, numeric: true,
        loadOptions: () => qhseApi.dechets.list(),
        mapRow: (r) => ({ value: String(r.id), label: r.libelle }),
      },
      { name: 'quantite', label: 'Quantité', type: 'number' },
      { name: 'producteur', label: 'Producteur', type: 'text' },
      { name: 'transporteur', label: 'Transporteur', type: 'text' },
      { name: 'eliminateur', label: 'Éliminateur', type: 'text' },
      { name: 'chantier_id', label: 'Chantier (id)', type: 'number' },
    ],
  },
  recyclageModules: {
    title: 'Nouveau recyclage PV', create: (d) => qhseApi.recyclageModules.create(d),
    fields: [
      { name: 'marque', label: 'Marque', type: 'text' },
      { name: 'modele', label: 'Modèle', type: 'text' },
      { name: 'nombre_modules', label: 'Nombre de modules', type: 'number', required: true, default: '1' },
      { name: 'masse_kg', label: 'Masse (kg)', type: 'number' },
      {
        name: 'motif', label: 'Motif', type: 'select', default: 'fin_de_vie',
        options: [
          { value: 'casse', label: 'Casse / bris' },
          { value: 'declassement', label: 'Déclassement (performance)' },
          { value: 'renovation', label: 'Rénovation / remplacement' },
          { value: 'fin_de_vie', label: 'Fin de vie' },
          { value: 'autre', label: 'Autre' },
        ],
      },
      { name: 'filiere', label: 'Filière', type: 'text' },
    ],
  },
  conformitesEnvironnementales: {
    title: 'Nouvelle conformité', create: (d) => qhseApi.conformitesEnvironnementales.create(d),
    fields: [
      { name: 'intitule', label: 'Intitulé', type: 'text', required: true },
      {
        name: 'type_conformite', label: 'Type', type: 'select', default: 'autorisation',
        options: [
          { value: 'autorisation', label: 'Autorisation environnementale' },
          { value: 'etude_impact', label: "Étude d'impact (EIE)" },
          { value: 'enregistrement_dechets', label: 'Enregistrement déchets' },
          { value: 'rejets', label: 'Conformité rejets (eau / air)' },
          { value: 'commission_locale', label: 'Commission locale (sécurité)' },
        ],
      },
      { name: 'autorite', label: 'Autorité', type: 'text' },
      { name: 'date_expiration', label: "Date d'expiration", type: 'date' },
    ],
  },
  bilansCarbone: {
    title: 'Nouveau bilan carbone', create: (d) => qhseApi.bilansCarbone.create(d),
    fields: [
      { name: 'libelle', label: 'Libellé', type: 'text', required: true },
      { name: 'annee', label: 'Année', type: 'number', required: true, default: String(CURRENT_YEAR) },
      { name: 'perimetre', label: 'Périmètre', type: 'text' },
    ],
  },
  indicateursEsg: {
    title: 'Nouvel indicateur ESG', create: (d) => qhseApi.indicateursEsg.create(d),
    fields: [
      { name: 'code', label: 'Code', type: 'text', required: true },
      { name: 'libelle', label: 'Libellé', type: 'text', required: true },
      {
        name: 'pilier', label: 'Pilier', type: 'select', default: 'environnement',
        options: [
          { value: 'environnement', label: 'Environnement' },
          { value: 'social', label: 'Social' },
          { value: 'gouvernance', label: 'Gouvernance' },
        ],
      },
      { name: 'valeur', label: 'Valeur', type: 'number' },
      { name: 'unite', label: 'Unité', type: 'text' },
      { name: 'annee', label: 'Année', type: 'number', default: String(CURRENT_YEAR) },
    ],
  },
  aspectsEnvironnementaux: {
    title: 'Nouvel aspect environnemental', create: (d) => qhseApi.aspectsEnvironnementaux.create(d),
    fields: [
      { name: 'activite', label: 'Activité', type: 'text', required: true },
      { name: 'aspect', label: 'Aspect', type: 'text', required: true },
      { name: 'impact', label: 'Impact', type: 'text' },
      {
        name: 'condition', label: 'Condition', type: 'select', default: 'normale',
        options: [
          { value: 'normale', label: 'Normale' },
          { value: 'anormale', label: 'Anormale' },
          { value: 'urgence', label: 'Urgence' },
        ],
      },
      { name: 'frequence', label: 'Fréquence', type: 'number' },
      { name: 'gravite', label: 'Gravité', type: 'number' },
    ],
  },
  relevesConsommation: {
    title: 'Nouveau relevé de consommation', create: (d) => qhseApi.relevesConsommation.create(d),
    fields: [
      { name: 'site_libelle', label: 'Site', type: 'text', required: true },
      {
        name: 'type_energie', label: "Type d'énergie", type: 'select', default: 'electricite',
        options: [
          { value: 'electricite', label: 'Électricité (kWh)' },
          { value: 'gasoil', label: 'Gasoil (L)' },
          { value: 'essence', label: 'Essence (L)' },
          { value: 'eau', label: 'Eau (m³)' },
        ],
      },
      { name: 'periode', label: 'Période', type: 'text' },
      { name: 'quantite', label: 'Quantité', type: 'number', required: true },
      {
        name: 'source', label: 'Source', type: 'select', default: 'facture',
        options: [
          { value: 'facture', label: 'Facture' },
          { value: 'compteur', label: 'Compteur' },
        ],
      },
    ],
  },
  demandesChangement: {
    title: 'Nouvelle demande de changement (MOC)', create: (d) => qhseApi.demandesChangement.create(d),
    fields: [
      {
        name: 'type_changement', label: 'Type', type: 'select', default: 'procede',
        options: [
          { value: 'procede', label: 'Procédé' },
          { value: 'equipement', label: 'Équipement' },
          { value: 'organisation', label: 'Organisation' },
          { value: 'document', label: 'Document' },
        ],
      },
      { name: 'description', label: 'Description', type: 'textarea', required: true },
      { name: 'justification', label: 'Justification', type: 'textarea' },
      {
        name: 'classification_impact', label: 'Impact', type: 'select', default: 'faible',
        options: [
          { value: 'faible', label: 'Faible' },
          { value: 'moyen', label: 'Moyen' },
          { value: 'fort', label: 'Fort' },
        ],
      },
    ],
  },
  veillesReglementaires: {
    title: 'Nouvelle veille réglementaire', create: (d) => qhseApi.veillesReglementaires.create(d),
    fields: [
      { name: 'texte_suivi', label: 'Texte suivi', type: 'text', required: true },
      { name: 'source', label: 'Source', type: 'text' },
      { name: 'cadence_jours', label: 'Cadence (jours)', type: 'number' },
    ],
  },
}

function EnvCreateDialog({ spec, onClose, onDone }) {
  const initial = useMemo(() => {
    const o = {}
    for (const f of spec.fields) o[f.name] = f.default ?? ''
    return o
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec])
  const [form, setForm] = useState(initial)
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState({})

  useEffect(() => {
    let cancelled = false
    spec.fields.filter((f) => f.type === 'loadedSelect').forEach((f) => {
      f.loadOptions()
        .then((r) => {
          const rows = r?.data?.results ?? r?.data ?? []
          if (!cancelled) {
            setLoaded((prev) => ({ ...prev, [f.name]: (Array.isArray(rows) ? rows : []).map(f.mapRow) }))
          }
        })
        .catch(() => {})
    })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec])

  const setField = (k, v) => setForm((prev) => ({ ...prev, [k]: v }))

  async function save() {
    for (const f of spec.fields) {
      if (f.required && (form[f.name] === '' || form[f.name] == null)) {
        toast.error(`${f.label} est requis.`); return
      }
    }
    const payload = {}
    for (const f of spec.fields) {
      const v = form[f.name]
      if (v === '' || v == null) continue
      payload[f.name] = (f.type === 'number' || f.numeric) ? Number(v) : v
    }
    setSaving(true)
    try {
      await spec.create(payload)
      toast.success('Enregistrement créé.')
      onDone(); onClose()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Création impossible.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogTitle>{spec.title}</DialogTitle>
        <div className="flex flex-col gap-3">
          {spec.fields.map((f) => {
            const opts = f.type === 'loadedSelect' ? (loaded[f.name] || []) : f.options
            const isSelect = f.type === 'select' || f.type === 'loadedSelect'
            return (
              <div key={f.name}>
                <Label>{f.label}{f.required ? ' *' : ''}</Label>
                {isSelect ? (
                  <FieldSelect
                    value={String(form[f.name] ?? '')}
                    onValueChange={(v) => setField(f.name, v)}
                    options={opts}
                  />
                ) : f.type === 'textarea' ? (
                  <Textarea rows={2} aria-label={f.label}
                    value={form[f.name]} onChange={(e) => setField(f.name, e.target.value)} />
                ) : (
                  <Input aria-label={f.label}
                    type={f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'}
                    value={form[f.name]} onChange={(e) => setField(f.name, e.target.value)} />
                )}
              </div>
            )
          })}
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onClose}>Annuler</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// WIR127 — bouton d'ouverture du dialogue de création d'un onglet.
function CreerButton({ onClick, label = 'Nouveau' }) {
  return (
    <Button size="sm" onClick={onClick}>
      <PlusCircle size={15} aria-hidden="true" /> {label}
    </Button>
  )
}

export default function Environnement() {
  const [tab, setTab] = useState('dechets')
  // WIR127 — état du dialogue de création (clé de spec) + nonce de rechargement.
  const [createKey, setCreateKey] = useState(null)
  const [reloadNonce, setReloadNonce] = useState(0)
  const bumpReload = () => setReloadNonce((n) => n + 1)

  const dechetsCols = useMemo(() => [
    { id: 'libelle', header: 'Déchet', accessor: (r) => r.libelle },
    { id: 'code', header: 'Code', width: 120, accessor: (r) => r.code || '—' },
    { id: 'categorie', header: 'Catégorie', width: 150, accessor: (r) => r.categorie_display || r.categorie },
    {
      id: 'dangereux', header: 'Dangereux', width: 110, align: 'center',
      accessor: (r) => r.dangereux,
      cell: (v) => <Badge tone={v ? 'danger' : 'neutral'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
    { id: 'mode', header: 'Traitement', width: 160, accessor: (r) => r.mode_traitement_display || r.mode_traitement },
  ], [])

  const bsdCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 130, accessor: (r) => r.reference },
    { id: 'dechet', header: 'Déchet', accessor: (r) => r.dechet_libelle || r.dechet },
    {
      id: 'quantite', header: 'Quantité', width: 120, align: 'right',
      accessor: (r) => r.quantite,
      cell: (v) => (v == null ? '—' : formatNumber(v, { decimals: 2 })),
    },
    { id: 'eliminateur', header: 'Éliminateur', accessor: (r) => r.eliminateur || '—' },
    {
      id: 'statut', header: 'Statut', width: 120,
      accessor: (r) => r.statut, cell: (v) => <BsdStatutPill status={v} />,
    },
  ], [])

  const recyclageCols = useMemo(() => [
    { id: 'reference', header: 'Réf.', width: 130, accessor: (r) => r.reference },
    { id: 'marque', header: 'Marque / modèle', accessor: (r) => [r.marque, r.modele].filter(Boolean).join(' ') || '—' },
    { id: 'nombre', header: 'Modules', width: 100, align: 'right', accessor: (r) => r.nombre_modules ?? 0 },
    { id: 'motif', header: 'Motif', width: 140, accessor: (r) => r.motif_display || r.motif },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut, cell: (v) => <RecyclageStatutPill status={v} />,
    },
  ], [])

  const conformiteCols = useMemo(() => [
    { id: 'intitule', header: 'Conformité', accessor: (r) => r.intitule },
    { id: 'type', header: 'Type', width: 170, accessor: (r) => r.type_conformite_display || r.type_conformite },
    { id: 'autorite', header: 'Autorité', accessor: (r) => r.autorite || '—' },
    {
      id: 'date_expiration', header: 'Expiration', width: 130, align: 'right',
      accessor: (r) => r.date_expiration, cell: (v) => formatDate(v),
    },
    {
      id: 'statut', header: 'Statut', width: 140,
      accessor: (r) => r.statut, cell: (v) => <ConformiteStatutPill status={v} />,
    },
  ], [])

  const bilanCols = useMemo(() => [
    { id: 'libelle', header: 'Bilan', accessor: (r) => r.libelle },
    { id: 'annee', header: 'Année', width: 90, align: 'right', accessor: (r) => r.annee ?? '—' },
    {
      id: 'total', header: 'Total tCO₂e', width: 140, align: 'right',
      accessor: (r) => num(r.total_tco2e) ?? 0,
      cell: (v) => formatNumber(v, { decimals: 2 }),
    },
    {
      id: 'statut', header: 'Statut', width: 120,
      accessor: (r) => r.statut, cell: (v) => <BilanStatutPill status={v} />,
    },
  ], [])

  const esgCols = useMemo(() => [
    { id: 'code', header: 'Code', width: 110, accessor: (r) => r.code },
    { id: 'libelle', header: 'Indicateur', accessor: (r) => r.libelle },
    {
      id: 'pilier', header: 'Pilier', width: 150,
      accessor: (r) => r.pilier, cell: (v) => <EsgPilierPill status={v} />,
    },
    {
      id: 'valeur', header: 'Valeur', width: 120, align: 'right',
      accessor: (r) => r.valeur,
      cell: (v, r) => `${formatNumber(v, {})}${r.unite ? ` ${r.unite}` : ''}`,
    },
    {
      id: 'atteinte_cible', header: 'Cible atteinte', width: 140, align: 'center',
      accessor: (r) => r.atteinte_cible,
      cell: (v) =>
        v == null
          ? <span className="text-muted-foreground">—</span>
          : <Badge tone={v ? 'success' : 'warning'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
  ], [])

  // XQHS20 — registre des aspects & impacts environnementaux (ISO 14001 6.1.2).
  const aspectsCols = useMemo(() => [
    { id: 'activite', header: 'Activité', accessor: (r) => r.activite },
    { id: 'aspect', header: 'Aspect', accessor: (r) => r.aspect },
    { id: 'impact', header: 'Impact', accessor: (r) => r.impact },
    {
      id: 'criticite', header: 'Criticité', width: 110, align: 'center',
      accessor: (r) => r.criticite ?? 0,
      cell: (v, r) => <Badge tone={r.significatif ? 'danger' : 'neutral'}>{v}</Badge>,
    },
    {
      id: 'significatif', header: 'Significatif', width: 120, align: 'center',
      accessor: (r) => r.significatif,
      cell: (v) => <Badge tone={v ? 'danger' : 'success'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
    {
      id: 'date_revue', header: 'Revue', width: 120, align: 'right',
      accessor: (r) => r.date_revue, cell: (v) => (v ? formatDate(v) : '—'),
    },
  ], [])

  // XQHS21 — relevés de consommation par site (bilan carbone en amont).
  const consommationCols = useMemo(() => [
    { id: 'site', header: 'Site', accessor: (r) => r.site_libelle },
    { id: 'type', header: 'Énergie', width: 130, accessor: (r) => r.type_energie_display || r.type_energie },
    { id: 'periode', header: 'Période', width: 120, accessor: (r) => r.periode },
    {
      id: 'quantite', header: 'Quantité', width: 120, align: 'right',
      accessor: (r) => r.quantite,
      cell: (v) => (v == null ? '—' : formatNumber(v, { decimals: 2 })),
    },
    { id: 'source', header: 'Source', width: 130, accessor: (r) => r.source_display || r.source },
  ], [])

  // XQHS24 — demandes de gestion du changement (MOC léger).
  const mocCols = useMemo(() => [
    { id: 'type', header: 'Type', width: 150, accessor: (r) => r.type_changement_display || r.type_changement },
    { id: 'description', header: 'Description', accessor: (r) => r.description },
    {
      id: 'impact', header: 'Impact', width: 120,
      accessor: (r) => r.classification_impact_display || r.classification_impact,
    },
    { id: 'statut', header: 'Statut', width: 140, accessor: (r) => r.statut_display || r.statut },
    {
      id: 'temporaire', header: 'Temporaire', width: 110, align: 'center',
      accessor: (r) => r.est_temporaire,
      cell: (v) => <Badge tone={v ? 'warning' : 'neutral'}>{v ? 'Oui' : 'Non'}</Badge>,
    },
  ], [])

  // XQHS26 — veille réglementaire QHSE Maroc.
  const veilleCols = useMemo(() => [
    { id: 'texte', header: 'Texte suivi', accessor: (r) => r.texte_suivi },
    { id: 'source', header: 'Source', accessor: (r) => r.source || '—' },
    {
      id: 'prochaine_revue', header: 'Prochaine revue', width: 150, align: 'right',
      accessor: (r) => r.date_prochaine_revue, cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'registre', header: 'Registre légal', width: 130, align: 'center',
      accessor: (r) => r.registre_conformite,
      cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Lié' : '—'}</Badge>,
    },
  ], [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2 className="flex items-center gap-2">
          <Leaf size={20} strokeWidth={1.75} aria-hidden="true" />
          Environnement & ESG
        </h2>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          <TabsTrigger value="dechets">Déchets</TabsTrigger>
          <TabsTrigger value="recyclage">Recyclage PV</TabsTrigger>
          <TabsTrigger value="conformite">Conformité</TabsTrigger>
          <TabsTrigger value="carbone">Bilan carbone</TabsTrigger>
          <TabsTrigger value="esg">ESG</TabsTrigger>
          <TabsTrigger value="aspects">Aspects environnementaux</TabsTrigger>
          <TabsTrigger value="changement">Changement & veille</TabsTrigger>
        </TabsList>

        <TabsContent value="dechets" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Référentiel des déchets"
            subtitle="Loi 28-00 — catégories & modes de traitement"
            fetcher={() => qhseApi.dechets.list()}
            columns={dechetsCols}
            exportName="qhse-dechets"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('dechets')} label="Nouveau déchet" />}
          />
          <QhseResourceList
            title="Bordereaux de suivi (BSD)"
            subtitle="Déchets dangereux — producteur → transporteur → éliminateur"
            fetcher={() => qhseApi.bordereauxDechets.list()}
            columns={bsdCols}
            exportName="qhse-bsd"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('bordereauxDechets')} label="Nouveau BSD" />}
          />
        </TabsContent>

        <TabsContent value="recyclage" className="mt-4">
          <QhseResourceList
            title="Recyclage des modules PV"
            subtitle="Collecte → transport → recyclage (filière)"
            fetcher={() => qhseApi.recyclageModules.list()}
            columns={recyclageCols}
            exportName="qhse-recyclage-modules"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('recyclageModules')} label="Nouveau recyclage" />}
          />
        </TabsContent>

        <TabsContent value="conformite" className="mt-4">
          <QhseResourceList
            title="Conformités environnementales"
            subtitle="Autorisations, études d’impact, rejets — échéances"
            fetcher={() => qhseApi.conformitesEnvironnementales.list()}
            columns={conformiteCols}
            exportName="qhse-conformites-env"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('conformitesEnvironnementales')} label="Nouvelle conformité" />}
          />
        </TabsContent>

        <TabsContent value="carbone" className="mt-4 flex flex-col gap-6">
          <BilanCarboneChart />
          <QhseResourceList
            title="Bilans carbone"
            subtitle="Scopes 1/2/3 (tCO₂e)"
            fetcher={() => qhseApi.bilansCarbone.list()}
            columns={bilanCols}
            exportName="qhse-bilans-carbone"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('bilansCarbone')} label="Nouveau bilan" />}
          />
        </TabsContent>

        <TabsContent value="esg" className="mt-4">
          <QhseResourceList
            title="Indicateurs ESG"
            subtitle="Environnement · Social · Gouvernance"
            fetcher={() => qhseApi.indicateursEsg.list()}
            columns={esgCols}
            exportName="qhse-indicateurs-esg"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('indicateursEsg')} label="Nouvel indicateur" />}
          />
        </TabsContent>

        <TabsContent value="aspects" className="mt-4 flex flex-col gap-6">
          <QhseResourceList
            title="Registre des aspects & impacts environnementaux"
            subtitle="ISO 14001 6.1.2 — criticité = fréquence × gravité vs seuil"
            fetcher={() => qhseApi.aspectsEnvironnementaux.list()}
            columns={aspectsCols}
            exportName="qhse-aspects-environnementaux"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('aspectsEnvironnementaux')} label="Nouvel aspect" />}
          />
          <QhseResourceList
            title="Relevés de consommation par site"
            subtitle="Électricité, eau, carburant — alimente le bilan carbone"
            fetcher={() => qhseApi.relevesConsommation.list()}
            columns={consommationCols}
            exportName="qhse-releves-consommation"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('relevesConsommation')} label="Nouveau relevé" />}
          />
        </TabsContent>

        <TabsContent value="changement" className="mt-4 flex flex-col gap-6">
          <CoutNonQualiteCard />
          <QhseResourceList
            title="Demandes de gestion du changement (MOC)"
            subtitle="Cycle de vie via transition serveur (jamais un PATCH direct du statut)"
            fetcher={() => qhseApi.demandesChangement.list()}
            columns={mocCols}
            exportName="qhse-demandes-changement"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('demandesChangement')} label="Nouvelle demande" />}
          />
          <QhseResourceList
            title="Veille réglementaire"
            subtitle="Textes suivis — revue périodique assistée"
            fetcher={() => qhseApi.veillesReglementaires.list()}
            columns={veilleCols}
            exportName="qhse-veille-reglementaire"
            deps={[reloadNonce]}
            actions={<CreerButton onClick={() => setCreateKey('veillesReglementaires')} label="Nouvelle veille" />}
          />
        </TabsContent>
      </Tabs>

      {/* WIR127 — dialogue de création générique (piloté par la spec de l'onglet) */}
      {createKey && (
        <EnvCreateDialog
          spec={ENV_CREATE_SPECS[createKey]}
          onClose={() => setCreateKey(null)}
          onDone={bumpReload}
        />
      )}
    </div>
  )
}
