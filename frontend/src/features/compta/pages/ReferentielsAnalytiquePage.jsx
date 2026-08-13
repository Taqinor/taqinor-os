import { useEffect, useState } from 'react'
import { Plus, Sparkles, Send, Trash2 } from 'lucide-react'
import { useTabParam } from '../components/useTabParam'
import { ListShell } from '../../../ui/module'
import {
  Button, Segmented,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label, Combobox, toast,
} from '../../../ui'
import comptaApi from '../../../api/comptaApi'
import useComptaList, { unwrap } from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT31 — Référentiels comptables parallèles et analytique multi-axes.
   ----------------------------------------------------------------------------
   4 ressources marquées « API-only » dans le commentaire même de comptaApi.js
   (NTFIN13/15/16/17) : livres parallèles (IFRS/GROUPE/FISCAL en plus du CGNC
   principal), ajustements de retraitement postés dans un référentiel
   parallèle (jamais dans le plan comptable principal), et axes analytiques
   configurables (Chantier/Région/Activité…) avec leurs imputations. Endpoints
   /compta/referentiels-comptables/, /ajustements-gaap/, /axes-analytiques/,
   /imputations-axes/.
   ========================================================================== */

const referentielsAsync = () => comptaApi.referentielsComptables.list()
  .then((res) => unwrap(res).map((r) => ({ value: r.id, label: `${r.code_display || r.code} — ${r.libelle}` })))

const axesAsync = () => comptaApi.axesAnalytiques.list()
  .then((res) => unwrap(res).map((a) => ({ value: a.id, label: `${a.code} — ${a.libelle}` })))

const centresAsync = () => comptaApi.centresCout.list()
  .then((res) => unwrap(res).map((c) => ({ value: c.id, label: `${c.code} — ${c.libelle}` })))

// ── NTFIN13 — Référentiels comptables / livres parallèles ──
function ReferentielsPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.referentielsComptables.list, undefined)

  const seed = async () => {
    try {
      await comptaApi.referentielsComptables.seed()
      toast.success('Référentiel CGNC principal amorcé.')
      list.reload()
    } catch {
      toast.error('Amorçage impossible.')
    }
  }

  const columns = [
    { id: 'code', header: 'Code', accessor: (r) => r.code_display || r.code },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'devise', header: 'Devise', accessor: (r) => r.devise_fonctionnelle, width: 90 },
    { id: 'principal', header: 'Principal', accessor: (r) => (r.est_principal ? 'Oui' : 'Non') },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non') },
  ]

  const fields = [
    { name: 'code', label: 'Code', options: [
      { value: 'CGNC', label: 'CGNC (Maroc)' }, { value: 'IFRS', label: 'IFRS' },
      { value: 'GROUPE', label: 'Référentiel de groupe' }, { value: 'FISCAL', label: 'Référentiel fiscal' },
    ] },
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'devise_fonctionnelle', label: 'Devise fonctionnelle' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="outline" onClick={seed}><Sparkles /> Amorcer le CGNC principal</Button>
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouveau référentiel</Button>
      </div>
      <ListShell
        hideHeader
        title="Référentiels comptables"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="referentiels-comptables"
        emptyTitle="Aucun référentiel"
        emptyDescription="Aucun livre parallèle amorcé — commencez par le CGNC principal."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouveau référentiel comptable"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.referentielsComptables.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN15 — Ajustements GAAP (postés dans un référentiel parallèle) ──
function PosterAjustementDialog({ onClose, onSaved }) {
  const [referentiel, setReferentiel] = useState(null)
  const [referentiels, setReferentiels] = useState([])
  const [motif, setMotif] = useState('')
  const [typeAjustement, setTypeAjustement] = useState('')
  const [lignes, setLignes] = useState([{ compte_numero: '', debit: '', credit: '', libelle: '' }])
  const [saving, setSaving] = useState(false)

  useEffect(() => { referentielsAsync().then(setReferentiels) }, [])

  const setLigne = (i, patch) => setLignes((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))
  const ajouterLigne = () => setLignes((prev) => [...prev, { compte_numero: '', debit: '', credit: '', libelle: '' }])
  const retirerLigne = (i) => setLignes((prev) => prev.filter((_, idx) => idx !== i))

  const submit = async (e) => {
    e.preventDefault()
    if (!referentiel) return
    setSaving(true)
    try {
      await comptaApi.ajustementsGaap.poster({
        referentiel, motif, type_ajustement: typeAjustement,
        lignes: lignes.filter((l) => l.compte_numero),
      })
      toast.success('Ajustement GAAP posté.')
      onSaved?.()
      onClose?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Postage impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader><DialogTitle>Poster un ajustement GAAP</DialogTitle></DialogHeader>
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="aj-ref" required>Référentiel</Label>
            <Combobox id="aj-ref" options={referentiels} value={referentiel} onChange={setReferentiel} />
          </div>
          <div className="flex gap-3">
            <div className="flex flex-1 flex-col gap-1">
              <Label htmlFor="aj-type">Type d'ajustement</Label>
              <Input id="aj-type" value={typeAjustement} onChange={(e) => setTypeAjustement(e.target.value)} />
            </div>
            <div className="flex flex-1 flex-col gap-1">
              <Label htmlFor="aj-motif" required>Motif</Label>
              <Input id="aj-motif" value={motif} onChange={(e) => setMotif(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-2 border-t pt-2">
            <span className="text-sm font-medium">Lignes (compte, débit, crédit)</span>
            {lignes.map((l, i) => (
              <div key={i} className="flex items-end gap-2">
                <Input placeholder="N° compte" value={l.compte_numero}
                  onChange={(e) => setLigne(i, { compte_numero: e.target.value })} />
                <Input placeholder="Débit" type="number" step="any" value={l.debit}
                  onChange={(e) => setLigne(i, { debit: e.target.value })} />
                <Input placeholder="Crédit" type="number" step="any" value={l.credit}
                  onChange={(e) => setLigne(i, { credit: e.target.value })} />
                <Input placeholder="Libellé" value={l.libelle}
                  onChange={(e) => setLigne(i, { libelle: e.target.value })} />
                <Button type="button" variant="ghost" size="icon" onClick={() => retirerLigne(i)}
                  aria-label="Retirer la ligne"><Trash2 className="size-4" /></Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={ajouterLigne}>
              <Plus /> Ajouter une ligne
            </Button>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving || !referentiel}>
              {saving ? 'Postage…' : 'Poster'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AjustementsGaapPanel() {
  const [dialog, setDialog] = useState(false)
  const list = useComptaList(comptaApi.ajustementsGaap.list, undefined)

  const columns = [
    { id: 'referentiel', header: 'Référentiel', accessor: (r) => r.referentiel,
      cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'type', header: 'Type', accessor: (r) => r.type_ajustement || '—' },
    { id: 'motif', header: 'Motif', accessor: (r) => r.motif || '—' },
    { id: 'ecriture', header: 'Écriture générée', accessor: (r) => (r.ecriture ? `#${r.ecriture}` : '—') },
    { id: 'reversible', header: 'Réversible', accessor: (r) => (r.reversible ? 'Oui' : 'Non') },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog(true)}><Send /> Poster un ajustement</Button>
      </div>
      <ListShell
        hideHeader
        title="Ajustements GAAP"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="ajustements-gaap"
        emptyTitle="Aucun ajustement"
        emptyDescription="Aucun retraitement posté dans un livre parallèle pour l'instant."
      />
      {dialog && <PosterAjustementDialog onClose={() => setDialog(false)} onSaved={list.reload} />}
    </div>
  )
}

// ── NTFIN16 — Axes analytiques configurables ──
function AxesPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.axesAnalytiques.list, undefined)

  const columns = [
    { id: 'code', header: 'Code', accessor: (r) => r.code, cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'ordre', header: 'Ordre', accessor: (r) => r.ordre, width: 80 },
    { id: 'actif', header: 'Actif', accessor: (r) => (r.actif ? 'Oui' : 'Non') },
  ]

  const fields = [
    { name: 'code', label: 'Code', required: true },
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'ordre', label: 'Ordre', type: 'number' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvel axe</Button>
      </div>
      <ListShell
        hideHeader
        title="Axes analytiques"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="axes-analytiques"
        emptyTitle="Aucun axe"
        emptyDescription="Aucun axe analytique configuré (ex. Chantier, Région, Activité)."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvel axe analytique"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.axesAnalytiques.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── NTFIN17 — Imputations analytiques multi-axes ──
function ImputationsPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.imputationsAxes.list, undefined)

  const columns = [
    { id: 'ligne', header: 'Ligne d’écriture', accessor: (r) => r.ligne_ecriture,
      cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'axe', header: 'Axe', accessor: (r) => r.axe, cell: (v) => <span className="font-mono text-xs">#{v}</span> },
    { id: 'centre', header: 'Centre / cible', accessor: (r) => r.centre_cout ?? '—' },
  ]

  const fields = [
    { name: 'ligne_ecriture', label: 'Ligne d’écriture (id)', type: 'number', required: true },
    { name: 'axe', label: 'Axe analytique', required: true, async: axesAsync },
    { name: 'centre_cout', label: 'Centre / cible', async: centresAsync },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvelle imputation</Button>
      </div>
      <ListShell
        hideHeader
        title="Imputations analytiques"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="imputations-axes"
        emptyTitle="Aucune imputation"
        emptyDescription="Aucune ligne d’écriture imputée sur un axe analytique."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvelle imputation analytique"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.imputationsAxes.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

const TABS = [
  { value: 'referentiels', label: 'Référentiels' },
  { value: 'ajustements', label: 'Ajustements GAAP' },
  { value: 'axes', label: 'Axes analytiques' },
  { value: 'imputations', label: 'Imputations' },
]

export default function ReferentielsAnalytiquePage() {
  const [tab, setTab] = useTabParam('referentiels')

  return (
    <div className="page">
      <div className="page-header">
        <h2>Référentiels & analytique multi-axes</h2>
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet référentiels & analytique" />
      </div>

      {tab === 'referentiels' && <ReferentielsPanel />}
      {tab === 'ajustements' && <AjustementsGaapPanel />}
      {tab === 'axes' && <AxesPanel />}
      {tab === 'imputations' && <ImputationsPanel />}
    </div>
  )
}
