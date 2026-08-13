import { useState } from 'react'
import { Plus, PackageCheck, AlertTriangle, Undo2, ArrowRightLeft, ListPlus } from 'lucide-react'
import { useTabParam } from '../components/useTabParam'
import { ListShell } from '../../../ui/module'
import {
  Button, Segmented, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList, { unwrap } from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT29 — Immobilisations avancées : composants, dépréciation, mutations,
   encours (CIP).
   ----------------------------------------------------------------------------
   5 ressources NTFIN40-43 greffées sur le module Immobilisations existant :
   composants amortis séparément (IAS 16), tests de dépréciation postables
   (IAS 36, impairment), mutations/transferts entre centres de coût, et les
   immobilisations en cours (CIP) avec leurs lignes de montants engagés —
   « Mis en service » bascule un CIP vers une immobilisation amortissable.
   Endpoints /compta/composants-immobilisation/, /depreciations-immobilisation/,
   /mutations-immobilisation/, /immobilisations-en-cours/,
   /lignes-immobilisation-en-cours/.
   ========================================================================== */

const immosAsync = () => comptaApi.immobilisations.list()
  .then((res) => unwrap(res).map((i) => ({
    value: i.id, label: `${i.reference} — ${i.libelle}`,
  })))

const centresAsync = () => comptaApi.centresCout.list()
  .then((res) => unwrap(res).map((c) => ({ value: c.id, label: `${c.code} — ${c.libelle}` })))

// ── NTFIN40 — Composants amortissables ──
function ComposantsPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.composantsImmobilisation.list, undefined)

  const columns = [
    { id: 'immobilisation', header: 'Immobilisation', accessor: (r) => r.immobilisation,
      cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'valeur', header: 'Valeur', accessor: (r) => Number(r.valeur) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'duree', header: 'Durée (ans)', accessor: (r) => r.duree_amortissement, width: 100 },
    { id: 'methode', header: 'Méthode', accessor: (r) => r.methode === 'degressif' ? 'Dégressif' : 'Linéaire' },
    { id: 'dotation', header: 'Dotation annuelle', accessor: (r) => Number(r.dotation_annuelle) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
  ]

  const fields = [
    { name: 'immobilisation', label: 'Immobilisation', required: true, async: immosAsync },
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'valeur', label: 'Valeur du composant', type: 'number', required: true },
    { name: 'duree_amortissement', label: "Durée d'amortissement (années)", type: 'number', required: true },
    { name: 'methode', label: 'Méthode', options: [
      { value: 'lineaire', label: 'Linéaire' }, { value: 'degressif', label: 'Dégressif' },
    ] },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouveau composant</Button>
      </div>
      <ListShell
        hideHeader
        title="Composants d'immobilisation"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="composants-immobilisation"
        emptyTitle="Aucun composant"
        emptyDescription="Aucun actif décomposé (structure/onduleur/panneaux) pour l'instant."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouveau composant d'immobilisation"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.composantsImmobilisation.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN41 — Tests de dépréciation (impairment) ──
function DepreciationsPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.depreciationsImmobilisation.list, undefined)

  const poster = async (row) => {
    try {
      await comptaApi.depreciationsImmobilisation.poster(row.id)
      toast.success('Dépréciation postée.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Postage impossible.'))
    }
  }

  const reprendre = async (row) => {
    const montant = window.prompt('Montant de la reprise :', String(row.perte_valeur || '0'))
    if (montant == null) return
    try {
      await comptaApi.depreciationsImmobilisation.reprendre(row.id, { montant: Number(montant) || 0 })
      toast.success('Reprise de dépréciation enregistrée.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Reprise impossible.'))
    }
  }

  const columns = [
    { id: 'immobilisation', header: 'Immobilisation', accessor: (r) => r.immobilisation,
      cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'date_test', header: 'Date du test', accessor: (r) => r.date_test, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'valeur_recuperable', header: 'Valeur recouvrable', accessor: (r) => Number(r.valeur_recuperable) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'valeur_comptable', header: 'Valeur comptable', accessor: (r) => Number(r.valeur_comptable) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'perte', header: 'Perte de valeur', accessor: (r) => Number(r.perte_valeur) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'etat', header: 'État', accessor: (r) => (r.reprise ? 'Reprise' : (r.ecriture ? 'Postée' : 'Non postée')) },
  ]

  const rowActions = (row) => {
    const acts = []
    if (!row.ecriture) acts.push({ id: 'poster', label: 'Poster', icon: AlertTriangle, onClick: () => poster(row) })
    else if (row.reversible && !row.reprise) {
      acts.push({ id: 'reprendre', label: 'Reprise de dépréciation', icon: Undo2, onClick: () => reprendre(row) })
    }
    return acts
  }

  const fields = [
    { name: 'immobilisation', label: 'Immobilisation', required: true, async: immosAsync },
    { name: 'date_test', label: 'Date du test', type: 'date', required: true },
    { name: 'valeur_recuperable', label: 'Valeur recouvrable', type: 'number', required: true },
    { name: 'valeur_comptable', label: 'Valeur comptable (VNC)', type: 'number', required: true },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouveau test</Button>
      </div>
      <ListShell
        hideHeader
        title="Tests de dépréciation (IAS 36)"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="depreciations-immobilisation"
        emptyTitle="Aucun test de dépréciation"
        emptyDescription="Aucun test de dépréciation enregistré."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouveau test de dépréciation"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.depreciationsImmobilisation.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN42 — Mutations / transferts ──
function MutationsPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.mutationsImmobilisation.list, undefined)

  const columns = [
    { id: 'immobilisation', header: 'Immobilisation', accessor: (r) => r.immobilisation,
      cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'ancien', header: 'Ancien centre', accessor: (r) => r.ancien_centre ?? '—' },
    { id: 'nouveau', header: 'Nouveau centre', accessor: (r) => r.nouveau_centre ?? '—' },
    { id: 'date', header: 'Date', accessor: (r) => r.date, searchable: false, cell: (v) => formatDate(v) },
    { id: 'motif', header: 'Motif', accessor: (r) => r.motif || '—' },
  ]

  const fields = [
    { name: 'immobilisation', label: 'Immobilisation', required: true, async: immosAsync },
    { name: 'ancien_centre', label: 'Ancien centre', async: centresAsync },
    { name: 'nouveau_centre', label: 'Nouveau centre', async: centresAsync },
    { name: 'date', label: 'Date de mutation', type: 'date', required: true },
    { name: 'motif', label: 'Motif' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><ArrowRightLeft /> Nouvelle mutation</Button>
      </div>
      <ListShell
        hideHeader
        title="Mutations / transferts d'immobilisation"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="mutations-immobilisation"
        emptyTitle="Aucune mutation"
        emptyDescription="Aucun transfert d'actif entre centres de coût enregistré."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvelle mutation d'immobilisation"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.mutationsImmobilisation.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN43 — Immobilisations en cours (CIP) + lignes ──
function EncoursLignesDialog({ encours, onClose, onChanged }) {
  const [lignes, setLignes] = useState(encours.lignes || [])
  const [libelle, setLibelle] = useState('')
  const [montant, setMontant] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [saving, setSaving] = useState(false)

  const ajouter = async (e) => {
    e.preventDefault()
    if (!montant) return
    setSaving(true)
    try {
      await comptaApi.lignesImmobilisationEnCours.create({
        encours: encours.id, libelle, montant: Number(montant) || 0, date,
      })
      const res = await comptaApi.immobilisationsEnCours.get(encours.id)
      setLignes(res.data?.lignes || [])
      setLibelle('')
      setMontant('')
      toast.success('Ligne ajoutée.')
      onChanged?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Ajout impossible.'))
    } finally {
      setSaving(false)
    }
  }

  const cumul = lignes.reduce((s, li) => s + (Number(li.montant) || 0), 0)

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Lignes engagées — {encours.libelle}</DialogTitle>
        </DialogHeader>
        {lignes.length === 0 ? (
          <EmptyState title="Aucune ligne" description="Aucun montant engagé sur ce chantier pour l'instant." />
        ) : (
          <ComptaTable
            aria-label="Lignes du CIP"
            rows={lignes}
            getRowKey={(li) => li.id}
            columns={[
              { key: 'libelle', label: 'Libellé', cell: (li) => li.libelle || '—' },
              { key: 'date', label: 'Date', cell: (li) => formatDate(li.date) },
              { key: 'montant', label: 'Montant', align: 'right', numeric: true,
                sortValue: (li) => Number(li.montant) || 0, cell: (li) => formatMAD(li.montant) },
            ]}
          />
        )}
        <p className="text-sm text-muted-foreground">Cumul affiché : {formatMAD(cumul)}</p>
        <form onSubmit={ajouter} noValidate className="flex flex-col gap-3 border-t pt-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="cip-libelle">Libellé</Label>
            <Input id="cip-libelle" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          </div>
          <div className="flex gap-3">
            <div className="flex flex-1 flex-col gap-1">
              <Label htmlFor="cip-montant" required>Montant</Label>
              <Input id="cip-montant" type="number" step="any" value={montant}
                onChange={(e) => setMontant(e.target.value)} />
            </div>
            <div className="flex flex-1 flex-col gap-1">
              <Label htmlFor="cip-date">Date</Label>
              <Input id="cip-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Ajout…' : 'Ajouter la ligne'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function EncoursPanel() {
  const [dialog, setDialog] = useState(null)
  const [lignesDe, setLignesDe] = useState(null)
  const list = useComptaList(comptaApi.immobilisationsEnCours.list, undefined)

  const mettreEnService = async (row) => {
    if (!window.confirm(`Mettre « ${row.libelle} » en service et créer l'immobilisation amortissable ?`)) return
    try {
      await comptaApi.immobilisationsEnCours.mettreEnService(row.id, {})
      toast.success('Immobilisation en cours mise en service.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Mise en service impossible.'))
    }
  }

  const columns = [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'compte', header: 'Compte (classe 23)', accessor: (r) => r.compte_encours,
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'cumule', header: 'Montant cumulé', accessor: (r) => Number(r.montant_cumule) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut },
    { id: 'mes', header: 'Mise en service', accessor: (r) => r.date_mise_en_service, searchable: false,
      cell: (v) => (v ? formatDate(v) : '—') },
  ]

  const rowActions = (row) => {
    const acts = [{ id: 'lignes', label: 'Lignes engagées', icon: ListPlus, onClick: () => setLignesDe(row) }]
    if (row.statut !== 'mis_en_service') {
      acts.push({ id: 'mes', label: 'Mettre en service', icon: PackageCheck, onClick: () => mettreEnService(row) })
    }
    return acts
  }

  const fields = [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'compte_encours', label: 'Compte immobilisation en cours (classe 23)' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouveau CIP</Button>
      </div>
      <ListShell
        hideHeader
        title="Immobilisations en cours (CIP)"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        onRowClick={(row) => setLignesDe(row)}
        exportName="immobilisations-en-cours"
        emptyTitle="Aucun chantier en cours"
        emptyDescription="Aucune immobilisation en cours de production."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvelle immobilisation en cours"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.immobilisationsEnCours.create(payload)}
          onSaved={list.reload}
        />
      )}
      {lignesDe && (
        <EncoursLignesDialog
          encours={lignesDe}
          onClose={() => setLignesDe(null)}
          onChanged={list.reload}
        />
      )}
    </div>
  )
}

const TABS = [
  { value: 'composants', label: 'Composants' },
  { value: 'depreciations', label: 'Dépréciations' },
  { value: 'mutations', label: 'Mutations' },
  { value: 'encours', label: 'Encours (CIP)' },
]

export default function ImmobilisationsAvanceesPage() {
  const [tab, setTab] = useTabParam('composants')

  return (
    <div className="page">
      <div className="page-header">
        <h2>Immobilisations avancées</h2>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet immobilisations avancées" />
      </div>

      {tab === 'composants' && <ComposantsPanel />}
      {tab === 'depreciations' && <DepreciationsPanel />}
      {tab === 'mutations' && <MutationsPanel />}
      {tab === 'encours' && <EncoursPanel />}
    </div>
  )
}
