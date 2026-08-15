import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTabParam } from '../components/useTabParam'
import { Plus, Pencil, RefreshCw, BookOpen, Send, Landmark } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Segmented, Card, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
// APX33 — le tableau PARTAGÉ de la compta (tri + export CSV) remplace les
// tables écrites à la main.
import ComptaTable from '../ComptaTable'
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
          <div>
            <ComptaTable
              aria-label="Position consolidée"
              exportName="position-consolidee"
              rows={comptes}
              getRowKey={(c, i) => c.id ?? i}
              columns={[
                { key: 'libelle', label: 'Compte', sortValue: (c) => c.libelle || `Compte #${c.id}`,
                  cell: (c) => c.libelle || `Compte #${c.id}` },
                { key: 'solde', label: 'Solde', align: 'right', numeric: true,
                  sortValue: (c) => Number(c.solde) || 0, cell: (c) => formatMAD(c.solde) },
              ]}
            />
            <div className="mt-3 flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
              <span className="text-muted-foreground">Total</span>
              <strong className="tabular-nums">{formatMAD(position.total)}</strong>
            </div>
          </div>
        )}
      </Card>

      <Card className="p-4 sm:p-5">
        <h3 className="mb-3 font-display text-base font-semibold">Prévisionnel roulant (13 semaines)</h3>
        {/* WIR182 — NTTRE18 : première semaine où le solde projeté passe sous
            zéro (`date_rupture_estimee`, racine de la réponse — jamais recalculé
            côté client). Absente/`null` = aucune rupture projetée. */}
        {previsionnel?.date_rupture_estimee && (
          <div className="mb-3 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
            Rupture de trésorerie projetée à partir du {formatDate(previsionnel.date_rupture_estimee)}.
          </div>
        )}
        {!semaines.length ? (
          <EmptyState title="Aucune donnée" description="Aucune ligne prévisionnelle." />
        ) : (
          <ComptaTable
            aria-label="Prévisionnel roulant"
            exportName="previsionnel-13-semaines"
            rows={semaines}
            getRowKey={(s, i) => i}
            columns={[
              { key: 'semaine', label: 'Semaine',
                sortValue: (s) => s.date_debut || '',
                cell: (s, i) => s.date_debut || `S${i + 1}` },
              { key: 'entrees', label: 'Entrées', align: 'right', numeric: true,
                sortValue: (s) => Number(s.entrees) || 0, cell: (s) => formatMAD(s.entrees) },
              { key: 'sorties', label: 'Sorties', align: 'right', numeric: true,
                sortValue: (s) => Number(s.sorties) || 0, cell: (s) => formatMAD(s.sorties) },
              { key: 'flux_net', label: 'Flux net', align: 'right', numeric: true,
                sortValue: (s) => Number(s.flux_net) || 0, cell: (s) => formatMAD(s.flux_net) },
              // WIR182 — la clé réelle est `solde_fin` (jamais `solde_projete`,
              // qui n'existe pas côté serveur : la colonne affichait « — »).
              { key: 'solde_fin', label: 'Solde projeté', align: 'right', numeric: true,
                sortValue: (s) => Number(s.solde_fin) || 0, cell: (s) => formatMAD(s.solde_fin) },
            ]}
          />
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
          <div className="max-h-60 overflow-y-auto">
            <ComptaTable
              aria-label="Journal de caisse"
              exportName="journal-caisse"
              rows={mouvements}
              getRowKey={(m, i) => m.id ?? i}
              columns={[
                { key: 'date', label: 'Date',
                  sortValue: (m) => m.date || m.date_mouvement || '',
                  cell: (m) => formatDate(m.date || m.date_mouvement) },
                { key: 'sens', label: 'Sens',
                  cell: (m) => (m.sens === 'entree' ? 'Entrée' : 'Sortie') },
                { key: 'motif', label: 'Motif', cell: (m) => m.motif || '—' },
                { key: 'montant', label: 'Montant', align: 'right', numeric: true,
                  sortValue: (m) => Number(m.montant) || 0, cell: (m) => formatMAD(m.montant) },
              ]}
            />
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

  // FG125 — poste l'écriture équilibrée du virement interne au grand livre.
  const posterVirement = async (row) => {
    try {
      await comptaApi.virements.poster(row.id)
      toast.success('Virement posté.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Postage impossible.'))
    }
  }

  const rowActions = (row) => {
    const acts = [{ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) }]
    if (tab === 'caisses') {
      acts.unshift({
        id: 'journal', label: 'Journal & clôture', icon: BookOpen,
        onClick: () => setCaisseJournal(row),
      })
    }
    if (tab === 'virements' && !row.posted) {
      acts.unshift({
        id: 'poster', label: 'Poster', icon: Landmark, onClick: () => posterVirement(row),
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
          hideHeader
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
