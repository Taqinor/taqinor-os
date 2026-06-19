import { useEffect, useMemo, useState } from 'react'
import { Undo2 } from 'lucide-react'
import stockApi from '../../api/stockApi'
import {
  StatusPill, DataTable,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button,
} from '../../ui'

// L744 — Liste consultable des RETOURS FOURNISSEUR (RetourFournisseurViewSet
// existait sans écran). Référence RF, fournisseur, statut, date + consultation
// du détail (lignes). Usage INTERNE (prix d'achat jamais client-facing) ; cette
// liste n'affiche aucun prix.

const RETOUR_STATUTS = {
  brouillon: 'Brouillon',
  valide: 'Validé',
  annule: 'Annulé',
}
const statutLabel = (s) => RETOUR_STATUTS[s] || s || ''

const fmtDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// ── Modal de consultation d'un retour (lecture seule) ───────────────────────
function RetourDetail({ retour, onClose }) {
  const lignes = retour?.lignes ?? []
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            Retour fournisseur — {retour.reference}
            <StatusPill status={retour.statut} label={statutLabel(retour.statut)} />
          </DialogTitle>
          <DialogDescription>
            Fournisseur : {retour.fournisseur_nom ?? '—'}
            {retour.bon_commande_reference ? ` · BCF ${retour.bon_commande_reference}` : ''}
            {' · '}{fmtDateFR(retour.date_creation)}
          </DialogDescription>
        </DialogHeader>

        {retour.motif && (
          <p className="rounded-lg border border-border bg-muted/40 p-3 text-sm">
            <span className="font-medium">Motif : </span>{retour.motif}
          </p>
        )}

        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[28rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Produit</th>
                <th className="px-3 py-2 text-left font-semibold">Quantité</th>
                <th className="px-3 py-2 text-left font-semibold">Motif</th>
              </tr>
            </thead>
            <tbody>
              {lignes.length === 0 && (
                <tr><td colSpan={3} className="px-3 py-3 text-muted-foreground">Aucune ligne.</td></tr>
              )}
              {lignes.map((l) => (
                <tr key={l.id} className="border-t border-border">
                  <td className="px-3 py-2">
                    {l.produit_nom}{l.produit_sku ? ` (${l.produit_sku})` : ''}
                  </td>
                  <td className="px-3 py-2 tabular-nums">{l.quantite}</td>
                  <td className="px-3 py-2">{l.motif || <span className="text-muted-foreground">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function RetoursFournisseur() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    stockApi.getRetoursFournisseur({ ordering: '-date_creation' })
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des retours impossible.'))
      .finally(() => setLoading(false))
  }, [])

  // Ouvre le détail en rechargeant la version complète (lignes à jour).
  const openRetour = async (r) => {
    try {
      const resp = await stockApi.getRetourFournisseur(r.id)
      setSelected(resp.data)
    } catch { setSelected(r) }
  }

  const columns = useMemo(() => [
    { id: 'reference', header: 'Référence', minWidth: 140,
      accessor: (r) => r.reference ?? '' },
    { id: 'fournisseur_nom', header: 'Fournisseur', minWidth: 160,
      accessor: (r) => r.fournisseur_nom ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'bon_commande_reference', header: 'BCF', width: 130,
      accessor: (r) => r.bon_commande_reference ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'statut', header: 'Statut', width: 120, searchable: false,
      accessor: (r) => r.statut,
      cell: (v) => <StatusPill status={v} label={statutLabel(v)} /> },
    { id: 'date_creation', header: 'Date', width: 120, searchable: false,
      accessor: (r) => r.date_creation,
      cell: (v) => fmtDateFR(v) },
    { id: 'lignes', header: 'Lignes', align: 'right', width: 90, searchable: false,
      accessor: (r) => (r.lignes ?? []).length },
  ], [])

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-2">
          <Undo2 className="size-5 text-muted-foreground" aria-hidden="true" />
          <div>
            <h1 className="font-display text-xl font-semibold tracking-tight">Retours fournisseur</h1>
            <p className="text-sm text-muted-foreground">{items.length} retour(s)</p>
          </div>
        </div>
      </header>

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <DataTable
        data={items}
        columns={columns}
        loading={loading}
        getRowId={(r) => r.id}
        searchPlaceholder="Rechercher (référence, fournisseur)…"
        globalColumns={['reference', 'fournisseur_nom']}
        onRowClick={openRetour}
        emptyTitle="Aucun retour fournisseur"
        emptyDescription="Les retours sont créés depuis un bon de commande fournisseur reçu."
        aria-label="Retours fournisseur"
      />

      {selected && (
        <RetourDetail retour={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
