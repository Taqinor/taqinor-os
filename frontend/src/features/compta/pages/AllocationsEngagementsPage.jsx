import { useEffect, useState } from 'react'
import { Plus, CheckCircle2, PlayCircle, Undo2, ListPlus, Landmark } from 'lucide-react'
import { useTabParam } from '../components/useTabParam'
import { ListShell } from '../../../ui/module'
import {
  Button, Segmented, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label, Combobox, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList, { unwrap } from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT32 — Clés de répartition et engagements budgétaires.
   ----------------------------------------------------------------------------
   NTFIN20-24 : les clés de répartition déversent une charge indirecte vers
   des centres cibles au prorata de coefficients (Σ = 100 %), les runs
   d'allocation exécutent ce déversement, les allocations récurrentes le
   planifient, et les engagements comptables réservent le budget dès le devis
   d'achat (avant la facture). PIÈGE DE NOMMAGE : une page « Engagements &
   clôtures avancées » existe déjà (retenues de garantie, cautions…) — un
   HOMONYME français sans rapport avec le backend /compta/engagements/ ici
   consommé. Endpoints /compta/cles-repartition/, /lignes-cle-repartition/,
   /allocations/, /allocations-recurrentes/, /engagements/.
   ========================================================================== */

const centresAsync = () => comptaApi.centresCout.list()
  .then((res) => unwrap(res).map((c) => ({ value: c.id, label: `${c.code} — ${c.libelle}` })))

const clesAsync = () => comptaApi.clesRepartition.list()
  .then((res) => unwrap(res).map((c) => ({ value: c.id, label: `${c.code} — ${c.libelle}` })))

const referentielsAsync = () => comptaApi.referentielsComptables.list()
  .then((res) => unwrap(res).map((r) => ({ value: r.id, label: `${r.code_display || r.code} — ${r.libelle}` })))

const comptesAsync = () => comptaApi.comptes.list()
  .then((res) => unwrap(res).map((c) => ({ value: c.id, label: `${c.numero} — ${c.intitule}` })))

// ── NTFIN20 — Clés de répartition + lignes (coefficients) ──
function LignesCleDialog({ cle, onClose, onChanged }) {
  const [lignes, setLignes] = useState(cle.lignes || [])
  const [centre, setCentre] = useState(null)
  const [centres, setCentres] = useState([])
  const [coefficient, setCoefficient] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => { centresAsync().then(setCentres) }, [])

  const total = lignes.reduce((s, l) => s + (Number(l.coefficient) || 0), 0)

  const ajouter = async (e) => {
    e.preventDefault()
    if (!centre || !coefficient) return
    setSaving(true)
    try {
      await comptaApi.lignesCleRepartition.create({
        cle: cle.id, centre_cout: centre, coefficient: Number(coefficient) || 0,
      })
      const res = await comptaApi.clesRepartition.get(cle.id)
      setLignes(res.data?.lignes || [])
      setCentre(null)
      setCoefficient('')
      toast.success('Ligne ajoutée.')
      onChanged?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Ajout impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-xl">
        <DialogHeader><DialogTitle>Coefficients — {cle.libelle}</DialogTitle></DialogHeader>
        {lignes.length === 0 ? (
          <EmptyState title="Aucun coefficient" description="Aucune cible pondérée pour cette clé." />
        ) : (
          <ComptaTable
            aria-label="Lignes de la clé de répartition"
            rows={lignes}
            getRowKey={(l) => l.id}
            columns={[
              { key: 'centre', label: 'Centre / axe cible', cell: (l) => l.centre_code || l.centre_cout },
              { key: 'coefficient', label: 'Coefficient (%)', align: 'right', numeric: true,
                sortValue: (l) => Number(l.coefficient) || 0, cell: (l) => `${l.coefficient} %` },
            ]}
          />
        )}
        <p className={`text-sm ${total === 100 ? 'text-success' : 'text-muted-foreground'}`}>
          Total des coefficients : {total} % {total === 100 ? '(équilibré)' : '(doit égaler 100 %)'}
        </p>
        <form onSubmit={ajouter} noValidate className="flex items-end gap-2 border-t pt-3">
          <div className="flex flex-1 flex-col gap-1">
            <Label htmlFor="lcr-centre">Centre / axe cible</Label>
            <Combobox id="lcr-centre" options={centres} value={centre} onChange={setCentre} />
          </div>
          <div className="flex flex-1 flex-col gap-1">
            <Label htmlFor="lcr-coef">Coefficient (%)</Label>
            <Input id="lcr-coef" type="number" step="any" value={coefficient}
              onChange={(e) => setCoefficient(e.target.value)} />
          </div>
          <Button type="submit" disabled={saving}>{saving ? 'Ajout…' : 'Ajouter'}</Button>
        </form>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ClesRepartitionPanel() {
  const [dialog, setDialog] = useState(null)
  const [lignesDe, setLignesDe] = useState(null)
  const list = useComptaList(comptaApi.clesRepartition.list, undefined)

  const valider = async (row) => {
    try {
      const res = await comptaApi.clesRepartition.valider(row.id)
      toast.success(`Clé équilibrée : ${res.data?.total_coefficients} % (100 % attendu).`)
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Les coefficients ne totalisent pas 100 %.'))
    }
  }

  const columns = [
    { id: 'code', header: 'Code', accessor: (r) => r.code, cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'type', header: 'Type', accessor: (r) => r.type_display || r.type_cle },
    { id: 'base', header: 'Base', accessor: (r) => r.base },
    { id: 'total', header: 'Σ coefficients', accessor: (r) => Number(r.total_coefficients) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => `${v} %` },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => [
    { id: 'lignes', label: 'Coefficients', icon: ListPlus, onClick: () => setLignesDe(row) },
    { id: 'valider', label: 'Valider (Σ = 100 %)', icon: CheckCircle2, onClick: () => valider(row) },
  ]

  const fields = [
    { name: 'code', label: 'Code', required: true },
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'type_cle', label: 'Type de clé', options: [
      { value: 'manuel', label: 'Manuel (coefficients saisis)' },
      { value: 'statistique', label: 'Statistique' },
      { value: 'proportionnel', label: 'Proportionnel' },
    ] },
    { name: 'base', label: 'Base de répartition', options: [
      { value: 'm2', label: 'Surface (m²)' }, { value: 'effectif', label: 'Effectifs' },
      { value: 'ca', label: "Chiffre d'affaires" }, { value: 'personnalisee', label: 'Base personnalisée' },
    ] },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvelle clé</Button>
      </div>
      <ListShell
        hideHeader
        title="Clés de répartition"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="cles-repartition"
        emptyTitle="Aucune clé"
        emptyDescription="Aucune clé de répartition de charge indirecte configurée."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvelle clé de répartition"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.clesRepartition.create(payload)}
          onSaved={list.reload}
        />
      )}
      {lignesDe && (
        <LignesCleDialog cle={lignesDe} onClose={() => setLignesDe(null)} onChanged={list.reload} />
      )}
    </div>
  )
}

// ── NTFIN21 — Runs d'allocation ──
function ExecuterDialog({ onClose, onSaved }) {
  const [cle, setCle] = useState(null)
  const [cles, setCles] = useState([])
  const [compteSource, setCompteSource] = useState('')
  const [periode, setPeriode] = useState(new Date().toISOString().slice(0, 10))
  const [montant, setMontant] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => { clesAsync().then(setCles) }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!cle || !compteSource || !periode) return
    setSaving(true)
    try {
      await comptaApi.allocations.executer({
        cle, compte_source: compteSource, periode, montant: montant || undefined,
      })
      toast.success('Allocation exécutée.')
      onSaved?.()
      onClose?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Exécution impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Exécuter une allocation</DialogTitle></DialogHeader>
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="ea-cle" required>Clé de répartition</Label>
            <Combobox id="ea-cle" options={cles} value={cle} onChange={setCle} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="ea-compte" required>Compte source</Label>
            <Input id="ea-compte" value={compteSource} onChange={(e) => setCompteSource(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="ea-periode" required>Période</Label>
            <Input id="ea-periode" type="date" value={periode} onChange={(e) => setPeriode(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="ea-montant">Montant (optionnel — sinon solde du compte)</Label>
            <Input id="ea-montant" type="number" step="any" value={montant}
              onChange={(e) => setMontant(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Exécution…' : 'Exécuter'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AllocationsPanel() {
  const [dialog, setDialog] = useState(false)
  const list = useComptaList(comptaApi.allocations.list, undefined)

  const reverser = async (row) => {
    try {
      await comptaApi.allocations.reverser(row.id)
      toast.success('Allocation extournée.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Extourne impossible.'))
    }
  }

  const columns = [
    { id: 'cle', header: 'Clé', accessor: (r) => r.cle, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'compte_source', header: 'Compte source', accessor: (r) => r.compte_source },
    { id: 'periode', header: 'Période', accessor: (r) => r.periode, searchable: false, cell: (v) => formatDate(v) },
    { id: 'montant', header: 'Montant réparti', accessor: (r) => Number(r.montant_reparti) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut },
  ]

  const rowActions = (row) => (row.statut === 'executee'
    ? [{ id: 'reverser', label: 'Reverser (extourner)', icon: Undo2, onClick: () => reverser(row) }]
    : [])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog(true)}><PlayCircle /> Exécuter une allocation</Button>
      </div>
      <ListShell
        hideHeader
        title="Runs d'allocation"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="allocations"
        emptyTitle="Aucun run"
        emptyDescription="Aucune allocation exécutée pour l'instant."
      />
      {dialog && <ExecuterDialog onClose={() => setDialog(false)} onSaved={list.reload} />}
    </div>
  )
}

// ── NTFIN22 — Allocations récurrentes ──
function AllocationsRecurrentesPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.allocationsRecurrentes.list, undefined)

  const toggleActif = async (row) => {
    try {
      await comptaApi.allocationsRecurrentes.update(row.id, { actif: !row.actif })
      toast.success(row.actif ? 'Allocation désactivée.' : 'Allocation activée.')
      list.reload()
    } catch {
      toast.error('Action impossible.')
    }
  }

  const columns = [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || `Clé #${r.cle}` },
    { id: 'compte_source', header: 'Compte source', accessor: (r) => r.compte_source },
    { id: 'periodicite', header: 'Périodicité', accessor: (r) => (r.periodicite === 'trimestrielle' ? 'Trimestrielle' : 'Mensuelle') },
    { id: 'prochaine', header: 'Prochaine échéance', accessor: (r) => r.prochaine_echeance, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non') },
  ]

  const rowActions = (row) => [
    { id: 'toggle', label: row.actif ? 'Désactiver' : 'Activer', onClick: () => toggleActif(row) },
  ]

  const fields = [
    { name: 'cle', label: 'Clé de répartition', required: true, async: clesAsync },
    { name: 'libelle', label: 'Libellé' },
    { name: 'compte_source', label: 'Compte source', required: true },
    { name: 'periodicite', label: 'Périodicité', options: [
      { value: 'mensuelle', label: 'Mensuelle' }, { value: 'trimestrielle', label: 'Trimestrielle' },
    ] },
    { name: 'prochaine_echeance', label: 'Prochaine échéance', type: 'date', required: true },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvelle allocation récurrente</Button>
      </div>
      <ListShell
        hideHeader
        title="Allocations récurrentes"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="allocations-recurrentes"
        emptyTitle="Aucune allocation récurrente"
        emptyDescription="Aucune allocation planifiée pour l'instant."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvelle allocation récurrente"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.allocationsRecurrentes.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN23-24 — Engagements comptables (encumbrance) ──
function EngagementsComptablesPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.engagementsComptables.list, undefined)

  const liquider = async (row) => {
    const montant = window.prompt('Montant à liquider :', String(row.montant_residuel || '0'))
    if (montant == null) return
    try {
      await comptaApi.engagementsComptables.liquider(row.id, { montant: Number(montant) || 0 })
      toast.success('Engagement liquidé (part consommée).')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Liquidation impossible.'))
    }
  }

  const columns = [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'type', header: 'Type', accessor: (r) => r.type_display || r.type_engagement },
    { id: 'compte', header: 'Compte', accessor: (r) => r.compte, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'montant_engage', header: 'Engagé', accessor: (r) => Number(r.montant_engage) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'montant_residuel', header: 'Résiduel', accessor: (r) => Number(r.montant_residuel) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut },
  ]

  const rowActions = (row) => (row.statut !== 'solde'
    ? [{ id: 'liquider', label: 'Liquider', icon: Landmark, onClick: () => liquider(row) }]
    : [])

  const fields = [
    { name: 'compte', label: 'Compte', required: true, async: comptesAsync },
    { name: 'centre_cout', label: 'Centre de coût', async: centresAsync },
    { name: 'referentiel', label: 'Référentiel (optionnel)', async: referentielsAsync },
    { name: 'type_engagement', label: "Type d'engagement", options: [
      { value: 'bon_commande', label: 'Bon de commande' },
      { value: 'note_frais', label: 'Note de frais' }, { value: 'marche', label: 'Marché' },
    ] },
    { name: 'reference', label: 'Référence' },
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'montant_engage', label: 'Montant engagé', type: 'number', required: true },
    { name: 'date_engagement', label: "Date d'engagement", type: 'date', required: true },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvel engagement</Button>
      </div>
      <ListShell
        hideHeader
        title="Engagements comptables"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="engagements-comptables"
        emptyTitle="Aucun engagement"
        emptyDescription="Aucun budget réservé pour l'instant (avant facturation)."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvel engagement comptable"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.engagementsComptables.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

const TABS = [
  { value: 'clesRepartition', label: 'Clés de répartition' },
  { value: 'allocations', label: "Runs d'allocation" },
  { value: 'allocationsRecurrentes', label: 'Allocations récurrentes' },
  { value: 'engagements', label: 'Engagements comptables' },
]

export default function AllocationsEngagementsPage() {
  const [tab, setTab] = useTabParam('clesRepartition')

  return (
    <div className="page">
      <div className="page-header">
        <h2>Allocations & engagements comptables</h2>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet allocations & engagements" />
      </div>

      {tab === 'clesRepartition' && <ClesRepartitionPanel />}
      {tab === 'allocations' && <AllocationsPanel />}
      {tab === 'allocationsRecurrentes' && <AllocationsRecurrentesPanel />}
      {tab === 'engagements' && <EngagementsComptablesPanel />}
    </div>
  )
}
