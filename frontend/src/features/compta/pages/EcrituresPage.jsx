import { useMemo, useState } from 'react'
import { Plus, Check, Undo2, Trash2 } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import {
  Button, Segmented, Input, Label, Combobox,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  HelpTip, toast,
} from '../../../ui'
import { formatMAD, formatDate, nbsp } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import { unwrap } from '../components/useComptaList.js'
import useResource from '../../../hooks/useResource'
import { totalDebit, totalCredit, ecart, estEquilibree } from '../ecritureBalance.js'

/* ============================================================================
   UX4 — Saisie d'écriture comptable (partie double).
   ----------------------------------------------------------------------------
   Liste filtrable (journal, période) + éditeur multi-lignes avec contrôle
   d'équilibre EN DIRECT (débit == crédit) : le bouton « Enregistrer » reste
   bloqué tant que l'écriture n'est pas équilibrée. Actions valider / extourner.
   Endpoints : /compta/ecritures/?journal=&date_debut=&date_fin= ,
   POST .../valider/ , POST .../extourner/.
   ========================================================================== */

const StatutEcriture = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  validee: { label: 'Validée', tone: 'success' },
  extournee: { label: 'Extournée', tone: 'warning' },
})

const emptyLigne = () => ({ compte: '', tiers_id: '', libelle: '', debit: '', credit: '' })

function LigneRow({ ligne, comptesOpts, onChange, onRemove, canRemove }) {
  return (
    <div className="grid grid-cols-[1.4fr_1.4fr_0.9fr_0.9fr_auto] items-center gap-2">
      <Combobox
        options={comptesOpts}
        value={ligne.compte || null}
        onChange={(v) => onChange({ ...ligne, compte: v })}
        placeholder="Compte…"
      />
      <Input
        placeholder="Libellé de ligne"
        value={ligne.libelle}
        onChange={(e) => onChange({ ...ligne, libelle: e.target.value })}
      />
      <Input
        type="number" step="any" inputMode="decimal" placeholder="Débit"
        value={ligne.debit}
        onChange={(e) => onChange({ ...ligne, debit: e.target.value, credit: e.target.value ? '' : ligne.credit })}
      />
      <Input
        type="number" step="any" inputMode="decimal" placeholder="Crédit"
        value={ligne.credit}
        onChange={(e) => onChange({ ...ligne, credit: e.target.value, debit: e.target.value ? '' : ligne.debit })}
      />
      <Button
        type="button" variant="ghost" size="icon"
        aria-label="Supprimer la ligne"
        disabled={!canRemove}
        onClick={onRemove}
      >
        <Trash2 className="size-4" />
      </Button>
    </div>
  )
}

function EcritureDialog({ open, onClose, journaux, comptesOpts, onSaved }) {
  const [journal, setJournal] = useState('')
  const [date, setDate] = useState('')
  const [libelle, setLibelle] = useState('')
  const [reference, setReference] = useState('')
  const [lignes, setLignes] = useState([emptyLigne(), emptyLigne()])
  const [saving, setSaving] = useState(false)

  const td = totalDebit(lignes)
  const tc = totalCredit(lignes)
  const diff = ecart(lignes)
  const balanced = estEquilibree(lignes)

  const setLigne = (i, next) =>
    setLignes((prev) => prev.map((l, idx) => (idx === i ? next : l)))
  const addLigne = () => setLignes((prev) => [...prev, emptyLigne()])
  const removeLigne = (i) =>
    setLignes((prev) => prev.filter((_, idx) => idx !== i))

  const submit = async (e) => {
    e.preventDefault()
    if (!balanced || !journal || !date) return
    const payload = {
      journal, date_ecriture: date, libelle, reference,
      lignes: lignes
        .filter((l) => l.compte)
        .map((l) => ({
          compte: l.compte,
          libelle: l.libelle || libelle,
          tiers_id: l.tiers_id || null,
          debit: l.debit ? Number(l.debit) : 0,
          credit: l.credit ? Number(l.credit) : 0,
        })),
    }
    setSaving(true)
    try {
      await comptaApi.ecritures.create(payload)
      toast.success('Écriture enregistrée.')
      onSaved?.()
      onClose?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d
        : (d?.detail || 'Enregistrement impossible — vérifiez les lignes.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-1.5">
            Nouvelle écriture
            {/* VX47 — aide contextuelle : la partie double n'est pas intuitive
                pour un nouvel employé. */}
            <HelpTip label="Aide — écriture comptable">
              Une écriture comptable est <strong>toujours équilibrée</strong> :
              le total des lignes au <strong>débit</strong> doit être strictement
              égal au total au <strong>crédit</strong>. Chaque ligne représente
              un mouvement sur un compte — un compte est débité, un autre est
              crédité pour le même montant. Le bouton « Enregistrer » reste
              bloqué tant que l'écart affiché ci-dessous n'est pas à zéro.
            </HelpTip>
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1">
              <Label required>Journal</Label>
              <select
                className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
                value={journal} onChange={(e) => setJournal(e.target.value)}
              >
                <option value="">—</option>
                {journaux.map((j) => (
                  <option key={j.id} value={j.id}>{j.code} — {j.libelle}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label required>Date</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Référence</Label>
              <Input value={reference} onChange={(e) => setReference(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <Label>Libellé</Label>
            <Input value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          </div>

          <div className="flex flex-col gap-2">
            <div className="grid grid-cols-[1.4fr_1.4fr_0.9fr_0.9fr_auto] gap-2 text-xs font-medium text-muted-foreground">
              <span>Compte</span><span>Libellé</span><span>Débit</span><span>Crédit</span><span />
            </div>
            {lignes.map((l, i) => (
              <LigneRow
                key={i}
                ligne={l}
                comptesOpts={comptesOpts}
                onChange={(next) => setLigne(i, next)}
                onRemove={() => removeLigne(i)}
                canRemove={lignes.length > 2}
              />
            ))}
            <Button type="button" variant="outline" size="sm" className="w-fit" onClick={addLigne}>
              <Plus className="size-4" /> Ajouter une ligne
            </Button>
          </div>

          {/* Bandeau d'équilibre EN DIRECT — le bouton reste bloqué si déséquilibré. */}
          <div
            className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm ${
              balanced ? 'border-success/40 bg-success/5' : 'border-destructive/40 bg-destructive/5'
            }`}
          >
            <span className="tabular-nums">{nbsp('Total débit :')} <strong>{formatMAD(td)}</strong></span>
            <span className="tabular-nums">{nbsp('Total crédit :')} <strong>{formatMAD(tc)}</strong></span>
            <span className={`tabular-nums font-medium ${balanced ? 'text-success' : 'text-destructive'}`}>
              {balanced ? 'Équilibrée ✓' : nbsp(`Écart : ${formatMAD(diff)}`)}
            </span>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving || !balanced || !journal || !date}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function EcrituresPage() {
  const [journalFilter, setJournalFilter] = useState('')
  const [showDialog, setShowDialog] = useState(false)

  // ARC45 — listes de référence (journaux + comptes), chargées une fois pour
  // l'éditeur ; erreurs silencieuses (comme avant), abort au démontage.
  const { data: journaux } = useResource(() => comptaApi.journaux.list(), undefined, {
    initialData: [], select: (res) => unwrap(res), errorMessage: () => '',
  })
  const { data: comptesOpts } = useResource(() => comptaApi.comptes.list(), undefined, {
    initialData: [],
    select: (res) => unwrap(res).map((c) => ({
      value: c.id, label: `${c.numero} — ${c.intitule}`,
    })),
    errorMessage: () => '',
  })

  const params = useMemo(
    () => (journalFilter ? { journal: journalFilter } : undefined), [journalFilter])
  // ARC45 — liste principale via useResource (remplace useComptaList) : même
  // comportement (unwrap DRF, toast d'erreur FR, refetch réactif au filtre).
  const { data: rows, loading, error, refetch: reload } = useResource(
    () => comptaApi.ecritures.list(params), params,
    {
      initialData: [],
      select: (res) => unwrap(res),
      errorMessage: () => {
        toast.error('Chargement impossible — réessayez.')
        return 'Chargement impossible.'
      },
    },
  )

  const valider = async (row) => {
    try {
      await comptaApi.ecritures.valider(row.id)
      toast.success('Écriture validée.')
      reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Validation impossible.'))
    }
  }
  const extourner = async (row) => {
    try {
      await comptaApi.ecritures.extourner(row.id)
      toast.success('Écriture extournée.')
      reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Extourne impossible.'))
    }
  }

  const columns = useMemo(() => [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference, width: 150,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'date', header: 'Date', accessor: (r) => r.date_ecriture, width: 120,
      searchable: false, cell: (v) => formatDate(v) },
    { id: 'journal', header: 'Journal', accessor: (r) => r.journal_code, width: 100 },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'debit', header: 'Débit', accessor: (r) => Number(r.total_debit) || 0,
      align: 'right', numeric: true, width: 140, searchable: false,
      cell: (v) => formatMAD(v) },
    { id: 'credit', header: 'Crédit', accessor: (r) => Number(r.total_credit) || 0,
      align: 'right', numeric: true, width: 140, searchable: false,
      cell: (v) => formatMAD(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, width: 130,
      searchable: false, cell: (v) => <StatutEcriture status={v} /> },
  ], [])

  const rowActions = (row) => {
    const acts = []
    if (row.statut === 'brouillon') {
      acts.push({ id: 'valider', label: 'Valider', icon: Check, onClick: () => valider(row) })
    }
    if (row.statut === 'validee') {
      acts.push({ id: 'extourner', label: 'Extourner', icon: Undo2, onClick: () => extourner(row) })
    }
    return acts
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Écritures comptables</h2>
        <div className="page-header-actions">
          <Button onClick={() => setShowDialog(true)}>
            <Plus /> Nouvelle écriture
          </Button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Segmented
          options={[
            { value: '', label: 'Tous journaux' },
            ...journaux.map((j) => ({ value: String(j.id), label: j.code })),
          ]}
          value={journalFilter}
          onChange={setJournalFilter}
          aria-label="Filtrer par journal"
        />
      </div>

      <ListShell
        title="Journal des écritures"
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        rowActions={rowActions}
        exportName="ecritures"
        emptyTitle="Aucune écriture"
        emptyDescription="Aucune écriture pour ce filtre."
      />

      {showDialog && (
        <EcritureDialog
          open
          onClose={() => setShowDialog(false)}
          journaux={journaux}
          comptesOpts={comptesOpts}
          onSaved={reload}
        />
      )}
    </div>
  )
}
