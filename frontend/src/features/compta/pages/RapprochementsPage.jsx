import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTabParam } from '../components/useTabParam'
import {
  Plus, Pencil, Lock, Unlock, CheckCircle2, Calculator, Wand2, Link2,
} from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import {
  Button, Segmented, Badge, Checkbox, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   UX9 — Rapprochements, budgets & clôtures.
   ----------------------------------------------------------------------------
   Onglets : rapprochements bancaires (+ panneau Suggestions XACC3, appariement
   noté par confiance, un-clic « accepter les non-ambiguës »), modèles de
   contrepartie automatique (XACC4), rapprochement 3 voies (bon-à-payer bloqué
   tant qu'il y a un écart), budgets, centres de coûts, exercices et périodes
   (verrouillage). Endpoints /compta/rapprochements/, /modeles-rapprochement/,
   /rapprochements-3voies/, /budgets/, /centres-cout/, /exercices/, /periodes/.
   ========================================================================== */

// VX229 — options du Combobox « Compte de contrepartie », chargées une fois à
// l'ouverture du CrudDialog (au lieu d'un champ FK « (ID) » tapé à la main).
const comptesAsync = () => comptaApi.comptes.list().then((res) => {
  const list = Array.isArray(res.data) ? res.data : (res.data?.results || [])
  return list.map((c) => ({ value: c.id, label: `${c.numero} — ${c.intitule}` }))
})

const TABS = [
  { value: 'bancaires', label: 'Bancaires' },
  { value: 'modeles', label: 'Modèles' },
  { value: 'troisVoies', label: '3 voies' },
  { value: 'budgets', label: 'Budgets' },
  { value: 'centres', label: 'Centres de coûts' },
  { value: 'exercices', label: 'Exercices' },
  { value: 'periodes', label: 'Périodes' },
]

// XACC3 — Suggestions d'appariement relevé ↔ GL, notées par confiance.
function SuggestionsDialog({ rapprochement, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    comptaApi.rapprochements.suggestions(rapprochement.id)
      .then((res) => setData(res.data))
      .catch(() => toast.error('Suggestions indisponibles.'))
      .finally(() => setLoading(false))
  }, [rapprochement.id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  const accepter = async () => {
    try {
      const res = await comptaApi.rapprochements.accepterSuggestions(rapprochement.id)
      const n = res.data?.acceptees?.length ?? res.data?.pointees ?? 0
      toast.success(`${n} ligne(s) pointée(s) automatiquement.`)
      load()
    } catch {
      toast.error('Acceptation impossible.')
    }
  }

  const suggestions = data?.suggestions || data?.lignes || []

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Suggestions d’appariement — {rapprochement.libelle}</DialogTitle>
        </DialogHeader>
        {loading ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Chargement…</p>
        ) : !suggestions.length ? (
          <EmptyState title="Aucune suggestion" description="Rien à apparier automatiquement pour l’instant." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-2 py-2">Ligne relevé</th>
                  <th className="px-2 py-2">Ligne GL</th>
                  <th className="px-2 py-2 text-right">Confiance</th>
                  <th className="px-2 py-2 text-right">Ambiguë</th>
                </tr>
              </thead>
              <tbody>
                {suggestions.map((s, i) => (
                  <tr key={i} className="border-b last:border-0">
                    <td className="px-2 py-1.5">{s.ligne_releve_libelle || s.ligne_releve || '—'}</td>
                    <td className="px-2 py-1.5">{s.ligne_gl_libelle || s.ligne_gl || '—'}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">
                      {s.confiance != null ? `${Math.round(s.confiance * 100)} %` : '—'}
                    </td>
                    <td className="px-2 py-1.5 text-right">
                      {s.ambigue ? <Badge tone="warning">Oui</Badge> : <Badge tone="success">Non</Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Fermer</Button>
          <Button onClick={accepter} disabled={loading || !suggestions.length}>
            <Wand2 className="size-4" /> Accepter les non-ambiguës
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// VX228 — Détail d'un rapprochement : 2 volets (relevé | grand-livre), pointage
// ligne-à-ligne, bandeau d'écart EN DIRECT (même langage visuel que le bandeau
// d'équilibre d'EcrituresPage). « Suggestions » est une action DE ce dialog.
function RapprochementDetailDialog({ rapprochement, onClose, onSaved }) {
  const [detail, setDetail] = useState(rapprochement)
  const [resume, setResume] = useState(null)
  const [gl, setGl] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedLigne, setSelectedLigne] = useState(null)
  const [selectedGl, setSelectedGl] = useState(new Set())
  const [pointing, setPointing] = useState(false)
  const [suggestionsOpen, setSuggestionsOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [d, r, g] = await Promise.all([
        comptaApi.rapprochements.get(rapprochement.id),
        comptaApi.rapprochements.resume(rapprochement.id),
        comptaApi.rapprochements.lignesGl(rapprochement.id),
      ])
      setDetail(d.data)
      setResume(r.data)
      setGl(Array.isArray(g.data) ? g.data : [])
    } catch {
      toast.error('Chargement du rapprochement impossible.')
    } finally {
      setLoading(false)
    }
  }, [rapprochement.id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const lignes = detail?.lignes_releve || []
  const ligneActive = lignes.find((l) => l.id === selectedLigne) || null

  // Candidates GL pré-filtrées montant/date sur la ligne relevé sélectionnée —
  // toujours réintégrer celles déjà appariées à CETTE ligne (pointer() remplace).
  const candidatesGl = useMemo(() => {
    const dejaSurLigne = new Set(ligneActive?.lignes_gl || [])
    const pool = gl.filter((g2) => !g2.pointee || dejaSurLigne.has(g2.id))
    if (!ligneActive) return pool
    const montant = Math.abs(Number(ligneActive.montant) || 0)
    return [...pool].sort((a, b) => {
      const da = Math.abs(Math.abs(Number(a.montant) || 0) - montant)
      const db = Math.abs(Math.abs(Number(b.montant) || 0) - montant)
      return da - db
    })
  }, [gl, ligneActive])

  const selectLigne = (l) => {
    setSelectedLigne(l.id)
    setSelectedGl(new Set(l.lignes_gl || []))
  }

  const toggleGl = (id, checked) => {
    setSelectedGl((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const pointer = async () => {
    if (!selectedLigne) return
    setPointing(true)
    try {
      await comptaApi.rapprochements.pointer(rapprochement.id, {
        ligne_releve: selectedLigne,
        lignes_gl: Array.from(selectedGl),
      })
      toast.success('Ligne pointée.')
      setSelectedLigne(null)
      setSelectedGl(new Set())
      await load()
      onSaved?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Pointage impossible.'))
    } finally {
      setPointing(false)
    }
  }

  const cloturer = async () => {
    try {
      await comptaApi.rapprochements.cloturer(rapprochement.id)
      toast.success('Rapprochement clôturé.')
      onSaved?.()
      onClose()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Clôture impossible.'))
    }
  }

  return (
    <>
      <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Rapprochement — {rapprochement.libelle}</DialogTitle>
          </DialogHeader>

          {/* Bandeau d'écart EN DIRECT — même langage visuel que l'équilibre d'écriture. */}
          <div
            className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm ${
              resume?.rapproche ? 'border-success/40 bg-success/5' : 'border-destructive/40 bg-destructive/5'
            }`}
          >
            <span className="tabular-nums">Solde relevé : <strong>{money(resume?.solde_releve)}</strong></span>
            <span className="tabular-nums">Solde pointé : <strong>{money(resume?.montant_pointe)}</strong></span>
            <span className={`tabular-nums font-medium ${resume?.rapproche ? 'text-success' : 'text-destructive'}`}>
              {resume?.rapproche ? 'Rapproché ✓' : `Écart : ${money(resume?.ecart)}`}
            </span>
            <span className="text-xs text-muted-foreground">
              {resume ? `${resume.lignes_pointees}/${resume.lignes_total} ligne(s) pointée(s)` : ''}
            </span>
          </div>

          {loading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Chargement…</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Relevé</h4>
                {!lignes.length ? (
                  <EmptyState title="Aucune ligne" description="Aucune ligne de relevé sur cette période." />
                ) : (
                  <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto">
                    {lignes.map((l) => (
                      <li key={l.id}>
                        <button
                          type="button"
                          onClick={() => selectLigne(l)}
                          className={`flex w-full items-center justify-between gap-2 rounded-md border px-2 py-1.5 text-left text-sm transition-colors ${
                            selectedLigne === l.id
                              ? 'border-primary bg-primary/5'
                              : 'border-transparent hover:bg-muted/50'
                          }`}
                        >
                          <span className="flex flex-col">
                            <span>{l.libelle || '—'}</span>
                            <span className="text-xs text-muted-foreground">{formatDate(l.date_operation)}</span>
                          </span>
                          <span className="flex items-center gap-2">
                            <span className="tabular-nums">{money(l.montant)}</span>
                            {l.est_concordante
                              ? <Badge tone="success">Pointée</Badge>
                              : <Badge tone="neutral">À pointer</Badge>}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="flex flex-col gap-2">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Grand-livre{ligneActive ? ` — candidates pour « ${ligneActive.libelle || '—'} »` : ''}
                </h4>
                {!selectedLigne ? (
                  <EmptyState title="Choisissez une ligne" description="Sélectionnez une ligne de relevé à gauche pour voir ses candidates." />
                ) : !candidatesGl.length ? (
                  <EmptyState title="Aucune candidate" description="Aucune ligne du grand-livre disponible sur la période." />
                ) : (
                  <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto">
                    {candidatesGl.map((g2) => (
                      <li key={g2.id}>
                        <label className="flex w-full items-center gap-2 rounded-md border border-transparent px-2 py-1.5 text-sm hover:bg-muted/50">
                          <Checkbox
                            checked={selectedGl.has(g2.id)}
                            onCheckedChange={(c) => toggleGl(g2.id, c === true)}
                          />
                          <span className="flex flex-1 flex-col">
                            <span>{g2.libelle || '—'}</span>
                            <span className="text-xs text-muted-foreground">{formatDate(g2.date)} · {g2.journal}</span>
                          </span>
                          <span className="tabular-nums">{money(g2.montant)}</span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          <DialogFooter className="flex-wrap gap-2">
            <Button variant="outline" onClick={() => setSuggestionsOpen(true)}>
              <Wand2 className="size-4" /> Suggestions
            </Button>
            {resume?.rapproche && (
              <Button variant="outline" onClick={cloturer}>
                <Lock className="size-4" /> Clôturer
              </Button>
            )}
            <Button onClick={pointer} disabled={!selectedLigne || pointing}>
              <Link2 className="size-4" /> {pointing ? 'Pointage…' : 'Pointer'}
            </Button>
            <Button variant="outline" onClick={onClose}>Fermer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {suggestionsOpen && (
        <SuggestionsDialog
          rapprochement={rapprochement}
          onClose={() => { setSuggestionsOpen(false); load(); onSaved?.() }}
        />
      )}
    </>
  )
}

const money = (v) => formatMAD(v)

const StatutRappro = statusPill({
  ouvert: { label: 'Ouvert', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'info' },
  rapproche: { label: 'Rapproché', tone: 'success' },
  concordant: { label: 'Concordant', tone: 'success' },
  ecart: { label: 'Écart', tone: 'danger' },
  valide: { label: 'Validé', tone: 'success' },
})

const StatutExercice = statusPill({
  ouvert: { label: 'Ouvert', tone: 'success' },
  cloture: { label: 'Clôturé', tone: 'neutral' },
})

export default function RapprochementsPage() {
  const [tab, setTab] = useTabParam('bancaires')  // VX231(c) — onglet persisté (?onglet=)
  const [dialog, setDialog] = useState(null)
  const [detailFor, setDetailFor] = useState(null)  // VX228 — RapprochementDetailDialog (contient
  // désormais l'action « Suggestions »)

  const fetcher = useMemo(() => ({
    bancaires: comptaApi.rapprochements.list,
    modeles: comptaApi.modelesRapprochement.list,
    troisVoies: comptaApi.rapprochements3voies.list,
    budgets: comptaApi.budgets.list,
    centres: comptaApi.centresCout.list,
    exercices: comptaApi.exercices.list,
    periodes: comptaApi.periodes.list,
  }[tab]), [tab])

  const list = useComptaList(fetcher, undefined)

  const act = async (fn, okMsg) => {
    try {
      await fn()
      toast.success(okMsg)
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Action impossible.'))
    }
  }

  // ── Colonnes par onglet ──
  const columns = useMemo(() => {
    switch (tab) {
      case 'bancaires':
        return [
          { id: 'compte', header: 'Compte', accessor: (r) => r.compte_libelle || '—' },
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'periode', header: 'Période', accessor: (r) => `${r.date_debut || ''} → ${r.date_fin || ''}`, searchable: false },
          { id: 'solde', header: 'Solde relevé', accessor: (r) => Number(r.solde_releve) || 0,
            align: 'right', numeric: true, searchable: false, cell: money },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
            cell: (v) => <StatutRappro status={v} /> },
        ]
      case 'modeles':
        return [
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'priorite', header: 'Priorité', accessor: (r) => r.priorite, width: 100 },
          { id: 'contrepartie', header: 'Contrepartie', accessor: (r) => r.compte_contrepartie_libelle || '—' },
        ]
      case 'troisVoies':
        return [
          { id: 'bc', header: 'Bon de commande', accessor: (r) => r.bon_commande_reference || '—' },
          { id: 'fourn', header: 'Fournisseur', accessor: (r) => r.fournisseur_nom || '—' },
          { id: 'cmd', header: 'Commandé', accessor: (r) => Number(r.montant_commande) || 0,
            align: 'right', numeric: true, searchable: false, cell: money },
          { id: 'facture', header: 'Facturé', accessor: (r) => Number(r.montant_facture) || 0,
            align: 'right', numeric: true, searchable: false, cell: money },
          { id: 'ecart', header: 'Écart', accessor: (r) => Number(r.ecart) || 0,
            align: 'right', numeric: true, searchable: false, cell: money },
          { id: 'bap', header: 'Bon à payer', accessor: (r) => (r.bon_a_payer ? 'Oui' : 'Non'),
            searchable: false,
            cell: (_v, r) => (r.bon_a_payer
              ? <Badge tone="success">Bon à payer</Badge>
              : <Badge tone="warning">Bloqué (écart)</Badge>) },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
            cell: (v) => <StatutRappro status={v} /> },
        ]
      case 'budgets':
        return [
          { id: 'annee', header: 'Année', accessor: (r) => r.annee, width: 100 },
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut, searchable: false },
        ]
      case 'centres':
        return [
          { id: 'code', header: 'Code', accessor: (r) => r.code, width: 120,
            cell: (v) => <span className="font-mono text-xs">{v}</span> },
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'axe', header: 'Axe', accessor: (r) => r.axe_display || r.axe || '—', searchable: false },
        ]
      case 'exercices':
        return [
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'periode', header: 'Période', accessor: (r) => `${r.date_debut || ''} → ${r.date_fin || ''}`, searchable: false },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
            cell: (v) => <StatutExercice status={v} /> },
        ]
      case 'periodes':
        return [
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'type', header: 'Type', accessor: (r) => r.type_periode_display || r.type_periode || '—', searchable: false },
          { id: 'periode', header: 'Période', accessor: (r) => `${r.date_debut || ''} → ${r.date_fin || ''}`, searchable: false },
          { id: 'verrou', header: 'Verrou', accessor: (r) => (r.verrouillee ? 'Verrouillée' : 'Ouverte'),
            searchable: false,
            cell: (_v, r) => (r.verrouillee
              ? <Badge tone="neutral">Verrouillée</Badge>
              : <Badge tone="success">Ouverte</Badge>) },
        ]
      default:
        return []
    }
  }, [tab])

  // ── Actions par ligne / onglet ──
  const rowActions = (row) => {
    switch (tab) {
      case 'bancaires':
        return [
          { id: 'ouvrir', label: 'Ouvrir le détail', icon: Link2,
            onClick: () => setDetailFor(row) },
          ...(row.statut !== 'rapproche' ? [{
            id: 'cloturer', label: 'Clôturer', icon: Lock,
            onClick: () => act(() => comptaApi.rapprochements.cloturer(row.id), 'Rapprochement clôturé.'),
          }] : []),
        ]
      case 'modeles':
        return [{ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) }]
      case 'troisVoies':
        return [
          { id: 'evaluer', label: 'Réévaluer', icon: Calculator,
            onClick: () => act(() => comptaApi.rapprochements3voies.evaluer(row.id), 'Rapprochement réévalué.') },
          // Validation possible UNIQUEMENT si bon à payer (aucun écart) — sinon bloqué.
          ...(row.bon_a_payer ? [{
            id: 'valider', label: 'Valider (bon à payer)', icon: CheckCircle2,
            onClick: () => act(() => comptaApi.rapprochements3voies.valider(row.id, {}), 'Rapprochement validé.'),
          }] : []),
        ]
      case 'exercices':
        return row.statut === 'cloture'
          ? [{ id: 'rouvrir', label: 'Rouvrir', icon: Unlock,
              onClick: () => act(() => comptaApi.exercices.rouvrir(row.id), 'Exercice rouvert.') }]
          : [{ id: 'cloturer', label: 'Clôturer', icon: Lock,
              onClick: () => act(() => comptaApi.exercices.cloturer(row.id), 'Exercice clôturé.') }]
      case 'periodes':
        return row.verrouillee
          ? [{ id: 'rouvrir', label: 'Rouvrir', icon: Unlock,
              onClick: () => act(() => comptaApi.periodes.rouvrir(row.id), 'Période rouverte.') }]
          : [{ id: 'cloturer', label: 'Verrouiller', icon: Lock,
              onClick: () => act(() => comptaApi.periodes.cloturer(row.id), 'Période verrouillée.') }]
      case 'centres':
        return [{ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) }]
      default:
        return []
    }
  }

  // Onglets avec création simple (centres de coûts, modèles de rapprochement).
  const canCreate = tab === 'centres' || tab === 'modeles'
  const submit = (payload) => {
    const api = tab === 'modeles' ? comptaApi.modelesRapprochement : comptaApi.centresCout
    return dialog?.row ? api.update(dialog.row.id, payload) : api.create(payload)
  }
  const createLabel = tab === 'modeles' ? 'Nouveau modèle' : 'Nouveau centre de coût'
  const dialogFields = tab === 'modeles'
    ? [
        { name: 'libelle', label: 'Libellé', required: true },
        { name: 'priorite', label: 'Priorité', type: 'number' },
        { name: 'compte_contrepartie', label: 'Compte de contrepartie', async: comptesAsync, required: true },
      ]
    : [
        { name: 'code', label: 'Code', required: true },
        { name: 'libelle', label: 'Libellé', required: true },
      ]

  return (
    <div className="page">
      <div className="page-header">
        <h2>Rapprochements & clôtures</h2>
        {canCreate && (
          <div className="page-header-actions">
            <Button onClick={() => setDialog({ row: null })}>
              <Plus /> {createLabel}
            </Button>
          </div>
        )}
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet rapprochements" />
      </div>

      <ListShell
        title={TABS.find((t) => t.value === tab).label}
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        onRowClick={tab === 'bancaires' ? (row) => setDetailFor(row) : undefined}
        rowActions={rowActions}
        exportName={tab}
        emptyTitle="Aucun élément"
        emptyDescription="Rien à afficher pour cet onglet."
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? `Modifier — ${createLabel.replace('Nouveau ', '')}` : createLabel}
          fields={dialogFields}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}

      {detailFor && (
        <RapprochementDetailDialog
          rapprochement={detailFor}
          onClose={() => setDetailFor(null)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}
