import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTabParam } from '../components/useTabParam'
import { Plus, Pencil, RefreshCw, BookOpen, Send } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Segmented, Card, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   UX6 — Trésorerie & prévisionnel.
   ----------------------------------------------------------------------------
   Onglets : comptes de trésorerie (banques), caisses, virements internes et
   lignes prévisionnelles. CRUD par onglet. Endpoints /compta/tresorerie/,
   /caisses/, /virements/, /previsionnel/. Onglet « Position » = lecture seule
   (FG122/FG126) : position consolidée + projection nette et prévisionnel
   roulant 13 semaines (GET /compta/etats/position-tresorerie/ et
   /compta/etats/previsionnel-tresorerie/).
   ========================================================================== */

const TABS = [
  { value: 'tresorerie', label: 'Comptes' },
  { value: 'caisses', label: 'Caisses' },
  { value: 'virements', label: 'Virements' },
  { value: 'previsionnel', label: 'Prévisionnel' },
  { value: 'position', label: 'Position & projection' },
]

const RESOURCE = {
  tresorerie: comptaApi.tresorerie,
  caisses: comptaApi.caisses,
  virements: comptaApi.virements,
  previsionnel: comptaApi.previsionnel,
}

const FIELDS = {
  tresorerie: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'banque', label: 'Banque' },
    { name: 'rib', label: 'RIB' },
    { name: 'iban', label: 'IBAN' },
    { name: 'solde_initial', label: 'Solde initial', type: 'number' },
  ],
  caisses: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'responsable', label: 'Responsable' },
    { name: 'solde_initial', label: 'Solde initial', type: 'number' },
  ],
  virements: [
    { name: 'date_virement', label: 'Date', type: 'date', required: true },
    { name: 'montant', label: 'Montant', type: 'number', required: true },
    { name: 'libelle', label: 'Libellé' },
    { name: 'reference', label: 'Référence' },
  ],
  previsionnel: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'date_prevue', label: 'Date prévue', type: 'date', required: true },
    { name: 'montant', label: 'Montant', type: 'number', required: true },
    { name: 'commentaire', label: 'Commentaire' },
  ],
}

const money = (v) => formatMAD(v)

const COLUMNS = {
  tresorerie: [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'banque', header: 'Banque', accessor: (r) => r.banque || '—' },
    { id: 'rib', header: 'RIB', accessor: (r) => r.rib || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'solde', header: 'Solde initial', accessor: (r) => Number(r.solde_initial) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
  caisses: [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'responsable', header: 'Responsable', accessor: (r) => r.responsable || '—' },
    { id: 'solde', header: 'Solde courant', accessor: (r) => Number(r.solde_courant ?? r.solde_initial) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
  virements: [
    { id: 'date', header: 'Date', accessor: (r) => r.date_virement, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'source', header: 'Source', accessor: (r) => r.source_libelle || '—' },
    { id: 'dest', header: 'Destination', accessor: (r) => r.destination_libelle || '—' },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
  previsionnel: [
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'categorie', header: 'Catégorie', accessor: (r) => r.categorie_display || r.categorie || '—' },
    { id: 'date', header: 'Date prévue', accessor: (r) => r.date_prevue, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
  ],
}

// Onglet lecture seule : position consolidée + prévisionnel roulant.
function PositionPanel() {
  const [position, setPosition] = useState(null)
  const [previsionnel, setPrevisionnel] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      comptaApi.etats.positionTresorerie(),
      comptaApi.etats.previsionnelTresorerie(),
    ])
      .then(([pos, prev]) => {
        setPosition(pos.data)
        setPrevisionnel(prev.data)
      })
      .catch(() => toast.error('Impossible de charger la position de trésorerie.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  if (loading) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Chargement…</p>
  }

  const comptes = position?.comptes || []
  const semaines = previsionnel?.semaines || previsionnel?.lignes || []

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4 sm:p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-display text-base font-semibold">Position consolidée</h3>
          <Button variant="outline" size="sm" onClick={load}><RefreshCw className="size-4" /> Actualiser</Button>
        </div>
        {!comptes.length ? (
          <EmptyState title="Aucune donnée" description="Aucun compte de trésorerie." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-2 py-2">Compte</th>
                  <th className="px-2 py-2 text-right">Solde</th>
                </tr>
              </thead>
              <tbody>
                {comptes.map((c, i) => (
                  <tr key={c.id ?? i} className="border-b last:border-0">
                    <td className="px-2 py-1.5">{c.libelle || `Compte #${c.id}`}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{formatMAD(c.solde)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-3 flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
              <span className="text-muted-foreground">Total</span>
              <strong className="tabular-nums">{formatMAD(position.total)}</strong>
            </div>
          </div>
        )}
      </Card>

      <Card className="p-4 sm:p-5">
        <h3 className="mb-3 font-display text-base font-semibold">Prévisionnel roulant (13 semaines)</h3>
        {!semaines.length ? (
          <EmptyState title="Aucune donnée" description="Aucune ligne prévisionnelle." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-2 py-2">Semaine</th>
                  <th className="px-2 py-2 text-right">Solde projeté</th>
                </tr>
              </thead>
              <tbody>
                {semaines.map((s, i) => (
                  <tr key={i} className="border-b last:border-0">
                    <td className="px-2 py-1.5">{s.date_debut || s.semaine || `S${i + 1}`}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">
                      {formatMAD(s.solde_projete ?? s.solde ?? s.montant)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

// FG124 — Journal d'espèces d'une caisse : mouvements + clôture (cash count).
function CaisseJournalDialog({ caisse, onClose }) {
  const [journal, setJournal] = useState(null)
  const [loading, setLoading] = useState(true)
  const [montant, setMontant] = useState('')
  const [motif, setMotif] = useState('')
  const [sens, setSens] = useState('entree')
  const [soldeCompte, setSoldeCompte] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    comptaApi.caisses.mouvementList(caisse.id)
      .then((res) => setJournal(res.data))
      .catch(() => toast.error('Journal de caisse indisponible.'))
      .finally(() => setLoading(false))
  }, [caisse.id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  const enregistrerMouvement = async () => {
    if (!(Number(montant) > 0)) {
      toast.error('Saisissez un montant positif.')
      return
    }
    try {
      await comptaApi.caisses.mouvementCreer(caisse.id, {
        sens, montant: Number(montant), motif,
        date_mouvement: new Date().toISOString().slice(0, 10),
      })
      toast.success('Mouvement enregistré.')
      setMontant('')
      setMotif('')
      load()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Enregistrement impossible.'))
    }
  }

  const cloturer = async () => {
    if (soldeCompte === '') {
      toast.error('Saisissez le solde compté avant de clôturer.')
      return
    }
    try {
      await comptaApi.caisses.cloturer(caisse.id, {
        date_cloture: new Date().toISOString().slice(0, 10),
        solde_compte: Number(soldeCompte),
      })
      toast.success('Caisse clôturée.')
      setSoldeCompte('')
      load()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Clôture impossible.'))
    }
  }

  const mouvements = Array.isArray(journal) ? journal : (journal?.mouvements || [])

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Journal de caisse — {caisse.libelle}</DialogTitle>
        </DialogHeader>
        {loading ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Chargement…</p>
        ) : !mouvements.length ? (
          <EmptyState title="Aucun mouvement" description="Aucun mouvement d’espèces enregistré." />
        ) : (
          <div className="max-h-60 overflow-y-auto overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-2 py-2">Date</th>
                  <th className="px-2 py-2">Sens</th>
                  <th className="px-2 py-2">Motif</th>
                  <th className="px-2 py-2 text-right">Montant</th>
                </tr>
              </thead>
              <tbody>
                {mouvements.map((m, i) => (
                  <tr key={m.id ?? i} className="border-b last:border-0">
                    <td className="px-2 py-1.5">{formatDate(m.date || m.date_mouvement)}</td>
                    <td className="px-2 py-1.5">{m.sens === 'entree' ? 'Entrée' : 'Sortie'}</td>
                    <td className="px-2 py-1.5">{m.motif || '—'}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{formatMAD(m.montant)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex flex-col gap-2 rounded-lg border p-3">
          <span className="text-sm font-semibold">Nouveau mouvement</span>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <select
              className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
              value={sens} onChange={(e) => setSens(e.target.value)}
            >
              <option value="entree">Entrée</option>
              <option value="sortie">Sortie</option>
            </select>
            <Input type="number" step="any" placeholder="Montant" value={montant}
                   onChange={(e) => setMontant(e.target.value)} />
            <Input placeholder="Motif" value={motif} onChange={(e) => setMotif(e.target.value)} />
          </div>
          <Button size="sm" className="w-fit" onClick={enregistrerMouvement}>
            <Plus className="size-4" /> Enregistrer le mouvement
          </Button>
        </div>

        <div className="flex flex-col gap-2 rounded-lg border p-3">
          <span className="text-sm font-semibold">Clôture (comptage physique)</span>
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor="cc-solde">Solde compté</Label>
              <Input id="cc-solde" type="number" step="any" value={soldeCompte}
                     onChange={(e) => setSoldeCompte(e.target.value)} />
            </div>
            <Button variant="outline" size="sm" onClick={cloturer}>
              <Send className="size-4" /> Clôturer la caisse
            </Button>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function TresoreriePage() {
  const [tab, setTab] = useTabParam('tresorerie')  // VX231(c) — onglet persisté (?onglet=)
  const [dialog, setDialog] = useState(null)
  const [caisseJournal, setCaisseJournal] = useState(null)

  const isPosition = tab === 'position'
  const list = useComptaList(
    isPosition ? comptaApi.exercices.list : RESOURCE[tab].list, undefined)

  const rowActions = (row) => {
    const acts = [{ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) }]
    if (tab === 'caisses') {
      acts.unshift({
        id: 'journal', label: 'Journal & clôture', icon: BookOpen,
        onClick: () => setCaisseJournal(row),
      })
    }
    return acts
  }

  const submit = (payload) => {
    const api = RESOURCE[tab]
    return dialog?.row ? api.update(dialog.row.id, payload) : api.create(payload)
  }

  const singular = useMemo(() => ({
    tresorerie: 'compte', caisses: 'caisse',
    virements: 'virement', previsionnel: 'ligne',
  }[tab]), [tab])

  return (
    <div className="page">
      <div className="page-header">
        <h2>Trésorerie & prévisionnel</h2>
        {!isPosition && (
          <div className="page-header-actions">
            <Button onClick={() => setDialog({ row: null })}>
              <Plus /> Nouveau {singular}
            </Button>
          </div>
        )}
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet trésorerie" />
      </div>

      {isPosition ? (
        <PositionPanel />
      ) : (
        <ListShell
          title={TABS.find((t) => t.value === tab).label}
          columns={COLUMNS[tab]}
          rows={list.rows}
          loading={list.loading}
          error={list.error}
          rowActions={rowActions}
          exportName={tab}
          emptyTitle="Aucun élément"
          emptyDescription="Rien à afficher pour cet onglet."
        />
      )}

      {dialog && !isPosition && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? `Modifier le ${singular}` : `Nouveau ${singular}`}
          fields={FIELDS[tab]}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}

      {caisseJournal && (
        <CaisseJournalDialog caisse={caisseJournal} onClose={() => setCaisseJournal(null)} />
      )}
    </div>
  )
}
