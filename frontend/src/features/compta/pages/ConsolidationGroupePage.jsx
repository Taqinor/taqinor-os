import { useEffect, useState } from 'react'
import { Plus, Lock, Unlock, DownloadCloud, Link2, Combine } from 'lucide-react'
import { useTabParam } from '../components/useTabParam'
import { ListShell } from '../../../ui/module'
import {
  Button, Segmented, Label, Combobox, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList, { unwrap } from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT33 — Consolidation groupe multi-sociétés.
   ----------------------------------------------------------------------------
   NTFIN1-9 : le cycle de consolidation pilote tout (ouvrir/verrouiller,
   collecter les liasses des filiales, apparier les intercos, générer les
   éliminations réciproques, marges internes et titres). Un cycle VERROUILLÉ
   refuse toute modification de collecte — le serveur renvoie 400, affiché ici
   TEL QUEL au lieu de planter. « EntiteConsolidation » (périmètre de filiales,
   mécanisme séparé et plus ancien) N'EST PAS fondu ici — hors périmètre.
   Endpoints /compta/cycles-consolidation/, /liasses-remontee/,
   /mappings-consolidation/, /operations-interco/, /marges-internes-stock/,
   /eliminations-titres/.
   ========================================================================== */

const exercicesAsync = () => comptaApi.exercices.list()
  .then((res) => unwrap(res).map((e) => ({ value: e.id, label: e.libelle })))

const cyclesAsync = () => comptaApi.cyclesConsolidation.list()
  .then((res) => unwrap(res).map((c) => ({ value: c.id, label: c.libelle })))

const comptesAsync = () => comptaApi.comptes.list()
  .then((res) => unwrap(res).map((c) => ({ value: c.id, label: `${c.numero} — ${c.intitule}` })))

function agirGenerique(fn, okMsg, onDone) {
  return fn().then(() => {
    toast.success(okMsg)
    onDone?.()
  }).catch((err) => {
    const d = err?.response?.data
    // Un cycle verrouillé refuse ici (400) — affiché TEL QUEL, jamais un plantage.
    toast.error(typeof d === 'string' ? d : (d?.detail || 'Action impossible.'))
  })
}

// ── NTFIN1 — Cycles de consolidation ──
function CyclesPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.cyclesConsolidation.list, undefined)

  const columns = [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'exercice', header: 'Exercice', accessor: (r) => r.exercice, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'periode', header: 'Période', accessor: (r) => r.date_debut, searchable: false,
      cell: (_v, r) => `${formatDate(r.date_debut)} → ${formatDate(r.date_fin)}` },
    { id: 'devise', header: 'Devise', accessor: (r) => r.devise_presentation, width: 90 },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut },
    { id: 'verrouille', header: 'Verrouillé', accessor: (r) => (r.verrouille ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => {
    const acts = [
      { id: 'collecter', label: 'Collecter les liasses', icon: DownloadCloud,
        onClick: () => agirGenerique(
          () => comptaApi.cyclesConsolidation.collecter(row.id, {}),
          'Collecte lancée pour le périmètre du cycle.', list.reload) },
    ]
    if (row.verrouille) {
      acts.push({ id: 'ouvrir', label: 'Ouvrir (déverrouiller)', icon: Unlock,
        onClick: () => agirGenerique(
          () => comptaApi.cyclesConsolidation.ouvrir(row.id),
          'Cycle rouvert.', list.reload) })
    } else {
      acts.push({ id: 'verrouiller', label: 'Verrouiller', icon: Lock,
        onClick: () => agirGenerique(
          () => comptaApi.cyclesConsolidation.verrouiller(row.id),
          'Cycle verrouillé — ses données agrégées sont figées.', list.reload) })
    }
    return acts
  }

  const fields = [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'exercice', label: 'Exercice', required: true, async: exercicesAsync },
    { name: 'date_debut', label: 'Début de période', type: 'date', required: true },
    { name: 'date_fin', label: 'Fin de période', type: 'date', required: true },
    { name: 'devise_presentation', label: 'Devise de présentation' },
    { name: 'tolerance_interco', label: 'Tolérance de matching interco', type: 'number' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouveau cycle</Button>
      </div>
      <ListShell
        hideHeader
        title="Cycles de consolidation"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="cycles-consolidation"
        emptyTitle="Aucun cycle"
        emptyDescription="Aucun cycle de consolidation ouvert pour l'instant."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouveau cycle de consolidation"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.cyclesConsolidation.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// Filtre partagé « Cycle » pour les onglets rattachés à un cycle.
function CycleFilterBar({ cycle, cycles, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <Label htmlFor="cf-cycle" className="text-sm text-muted-foreground">Filtrer par cycle</Label>
      <Combobox id="cf-cycle" options={cycles} value={cycle} onChange={onChange} clearable />
    </div>
  )
}

// ── NTFIN2 — Liasses de remontée (lecture seule, collectées via le cycle) ──
function LiassesPanel() {
  const [cycle, setCycle] = useState(null)
  const [cycles, setCycles] = useState([])
  useEffect(() => { cyclesAsync().then(setCycles) }, [])
  const list = useComptaList(comptaApi.liassesRemontee.list, { cycle: cycle || undefined })

  const columns = [
    { id: 'cycle', header: 'Cycle', accessor: (r) => r.cycle, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'entite', header: 'Entité (société membre)', accessor: (r) => r.entite, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'devise', header: 'Devise locale', accessor: (r) => r.devise_locale, width: 100 },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut },
    { id: 'collectee', header: 'Collectée le', accessor: (r) => r.date_collecte, searchable: false,
      cell: (v) => (v ? formatDate(v) : '—') },
  ]

  return (
    <div className="flex flex-col gap-3">
      <CycleFilterBar cycle={cycle} cycles={cycles} onChange={setCycle} />
      <ListShell
        hideHeader
        title="Liasses de remontée"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="liasses-remontee"
        emptyTitle="Aucune liasse"
        emptyDescription="Aucune balance collectée — utilisez « Collecter les liasses » sur un cycle."
      />
    </div>
  )
}

// ── NTFIN4 — Mappings compte local → compte groupe ──
function MappingsPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.mappingsConsolidation.list, undefined)

  const toggleActif = async (row) => {
    try {
      await comptaApi.mappingsConsolidation.update(row.id, { actif: !row.actif })
      toast.success(row.actif ? 'Mapping désactivé.' : 'Mapping activé.')
      list.reload()
    } catch {
      toast.error('Action impossible.')
    }
  }

  const columns = [
    { id: 'prefixe', header: 'Préfixe local', accessor: (r) => r.plan_local_prefixe, cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'compte_groupe', header: 'Compte de groupe', accessor: (r) => r.compte_groupe_numero || r.compte_groupe },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || '—' },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => [
    { id: 'toggle', label: row.actif ? 'Désactiver' : 'Activer', onClick: () => toggleActif(row) },
  ]

  const fields = [
    { name: 'plan_local_prefixe', label: 'Préfixe de compte local', required: true },
    { name: 'compte_groupe', label: 'Compte de groupe', required: true, async: comptesAsync },
    { name: 'libelle', label: 'Libellé' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouveau mapping</Button>
      </div>
      <ListShell
        hideHeader
        title="Mappings de consolidation"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="mappings-consolidation"
        emptyTitle="Aucun mapping"
        emptyDescription="Aucune correspondance plan local → compte de groupe."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouveau mapping de consolidation"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.mappingsConsolidation.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN6 — Opérations inter-sociétés ──
function IntercosPanel() {
  const [cycle, setCycle] = useState(null)
  const [cycles, setCycles] = useState([])
  const [dialog, setDialog] = useState(null)
  useEffect(() => { cyclesAsync().then(setCycles) }, [])
  const list = useComptaList(comptaApi.operationsInterco.list, { cycle: cycle || undefined })

  const apparier = () => {
    if (!cycle) { toast.error('Choisissez un cycle à apparier.'); return }
    agirGenerique(() => comptaApi.cyclesConsolidation.apparier(cycle), 'Opérations réciproques appariées.', list.reload)
  }

  const columns = [
    { id: 'debit', header: 'Entité débitrice', accessor: (r) => r.entite_debit, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'credit', header: 'Entité créditrice', accessor: (r) => r.entite_credit, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'compte', header: 'Compte réciproque', accessor: (r) => r.compte_reciproque },
    { id: 'montant_a', header: 'Déclaré (débit)', accessor: (r) => Number(r.montant_declare_a) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'montant_b', header: 'Déclaré (crédit)', accessor: (r) => Number(r.montant_declare_b) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'ecart', header: 'Écart', accessor: (r) => Number(r.ecart) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut },
  ]

  const fields = [
    { name: 'cycle', label: 'Cycle', required: true, async: cyclesAsync },
    { name: 'entite_debit', label: 'Entité débitrice (id société)', type: 'number', required: true },
    { name: 'entite_credit', label: 'Entité créditrice (id société)', type: 'number', required: true },
    { name: 'compte_reciproque', label: 'Compte réciproque (CGNC)', required: true },
    { name: 'libelle', label: 'Libellé' },
    { name: 'montant_declare_a', label: 'Montant déclaré (débit)', type: 'number' },
    { name: 'montant_declare_b', label: 'Montant déclaré (crédit)', type: 'number' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <CycleFilterBar cycle={cycle} cycles={cycles} onChange={setCycle} />
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={apparier}><Link2 /> Apparier ce cycle</Button>
          <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvelle opération</Button>
        </div>
      </div>
      <ListShell
        hideHeader
        title="Opérations inter-sociétés"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="operations-interco"
        emptyTitle="Aucune opération"
        emptyDescription="Aucune opération réciproque déclarée pour ce cycle."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvelle opération inter-sociétés"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.operationsInterco.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN8 — Marges internes sur stock ──
function MargesPanel() {
  const [cycle, setCycle] = useState(null)
  const [cycles, setCycles] = useState([])
  const [dialog, setDialog] = useState(null)
  useEffect(() => { cyclesAsync().then(setCycles) }, [])
  const list = useComptaList(comptaApi.margesInternesStock.list, { cycle: cycle || undefined })

  const eliminer = (row) => agirGenerique(
    () => comptaApi.margesInternesStock.eliminer(row.id), 'Marge interne éliminée.', list.reload)

  const columns = [
    { id: 'vendeuse', header: 'Entité vendeuse', accessor: (r) => r.entite_vendeuse, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'acheteuse', header: 'Entité acheteuse', accessor: (r) => r.entite_acheteuse, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'montant_stock', header: 'Stock détenu', accessor: (r) => Number(r.montant_stock) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'taux_marge', header: 'Taux de marge', accessor: (r) => Number(r.taux_marge) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => `${v} %` },
    { id: 'marge', header: 'Marge non réalisée', accessor: (r) => Number(r.marge_non_realisee) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'elimine', header: 'Éliminée', accessor: (r) => (r.elimination ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => (!row.elimination
    ? [{ id: 'eliminer', label: 'Éliminer', icon: Combine, onClick: () => eliminer(row) }]
    : [])

  const fields = [
    { name: 'cycle', label: 'Cycle', required: true, async: cyclesAsync },
    { name: 'entite_vendeuse', label: 'Entité vendeuse (id société)', type: 'number', required: true },
    { name: 'entite_acheteuse', label: 'Entité acheteuse (id société)', type: 'number', required: true },
    { name: 'montant_stock', label: 'Montant du stock détenu', type: 'number', required: true },
    { name: 'taux_marge', label: 'Taux de marge (%)', type: 'number' },
    { name: 'taux_impot', label: "Taux d'impôt différé (%)", type: 'number' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <CycleFilterBar cycle={cycle} cycles={cycles} onChange={setCycle} />
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvelle marge interne</Button>
      </div>
      <ListShell
        hideHeader
        title="Marges internes sur stock"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="marges-internes-stock"
        emptyTitle="Aucune marge interne"
        emptyDescription="Aucun stock inter-sociétés à éliminer pour ce cycle."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvelle marge interne sur stock"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.margesInternesStock.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN9 — Éliminations de titres ──
function EliminationsTitresPanel() {
  const [cycle, setCycle] = useState(null)
  const [cycles, setCycles] = useState([])
  const [dialog, setDialog] = useState(null)
  useEffect(() => { cyclesAsync().then(setCycles) }, [])
  const list = useComptaList(comptaApi.eliminationsTitres.list, { cycle: cycle || undefined })

  const eliminer = (row) => agirGenerique(
    () => comptaApi.eliminationsTitres.eliminer(row.id), 'Titres éliminés.', list.reload)

  const columns = [
    { id: 'fille', header: 'Entité fille', accessor: (r) => r.entite_fille, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'valeur_titres', header: 'Valeur des titres', accessor: (r) => Number(r.valeur_titres) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'quote_part', header: 'Quote-part capitaux propres', accessor: (r) => Number(r.quote_part_capitaux_propres) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'ecart', header: 'Écart d’acquisition', accessor: (r) => Number(r.ecart_acquisition) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'methode', header: 'Méthode', accessor: (r) => r.methode_display || r.methode },
    { id: 'elimine', header: 'Éliminée', accessor: (r) => (r.elimination ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => (!row.elimination
    ? [{ id: 'eliminer', label: 'Éliminer', icon: Combine, onClick: () => eliminer(row) }]
    : [])

  const fields = [
    { name: 'cycle', label: 'Cycle', required: true, async: cyclesAsync },
    { name: 'entite_fille', label: 'Entité fille (id société)', type: 'number', required: true },
    { name: 'valeur_titres', label: 'Valeur des titres', type: 'number', required: true },
    { name: 'quote_part_capitaux_propres', label: 'Quote-part capitaux propres', type: 'number', required: true },
    { name: 'methode', label: 'Méthode', options: [
      { value: 'acquisition', label: "Méthode de l'acquisition" },
      { value: 'equivalence', label: 'Mise en équivalence' },
    ] },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <CycleFilterBar cycle={cycle} cycles={cycles} onChange={setCycle} />
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvelle élimination</Button>
      </div>
      <ListShell
        hideHeader
        title="Éliminations de titres"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="eliminations-titres"
        emptyTitle="Aucune élimination"
        emptyDescription="Aucun titre de participation à éliminer pour ce cycle."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvelle élimination de titres"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.eliminationsTitres.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

const TABS = [
  { value: 'cycles', label: 'Cycles' },
  { value: 'liasses', label: 'Liasses' },
  { value: 'mappings', label: 'Mappings' },
  { value: 'intercos', label: 'Intercos' },
  { value: 'marges', label: 'Marges internes' },
  { value: 'titres', label: 'Éliminations titres' },
]

export default function ConsolidationGroupePage() {
  const [tab, setTab] = useTabParam('cycles')

  return (
    <div className="page">
      <div className="page-header">
        <h2>Consolidation groupe</h2>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet consolidation groupe" />
      </div>

      {tab === 'cycles' && <CyclesPanel />}
      {tab === 'liasses' && <LiassesPanel />}
      {tab === 'mappings' && <MappingsPanel />}
      {tab === 'intercos' && <IntercosPanel />}
      {tab === 'marges' && <MargesPanel />}
      {tab === 'titres' && <EliminationsTitresPanel />}
    </div>
  )
}
