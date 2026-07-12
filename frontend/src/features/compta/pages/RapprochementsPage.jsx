import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTabParam } from '../components/useTabParam'
import {
  Plus, Pencil, Lock, Unlock, CheckCircle2, Calculator, Wand2,
} from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import {
  Button, Segmented, Badge, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'
import { formatMAD } from '../../../lib/format'
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
  const [suggestionsFor, setSuggestionsFor] = useState(null)

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
          { id: 'suggestions', label: 'Suggestions (auto-appariement)', icon: Wand2,
            onClick: () => setSuggestionsFor(row) },
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
        { name: 'compte_contrepartie', label: 'Compte de contrepartie (ID)', required: true },
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

      {suggestionsFor && (
        <SuggestionsDialog rapprochement={suggestionsFor} onClose={() => setSuggestionsFor(null)} />
      )}
    </div>
  )
}
