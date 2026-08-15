import { useEffect, useMemo, useState } from 'react'
import { Undo2,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import {
  StatusPill, DataTable,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button,
} from '../../ui'
// APX24 — en-tête UNIQUE de l'app (VX28) + accent de la famille inventaire :
// les 15 écrans Stock parlaient chacun leur propre idiome d'en-tête.
import { PageHeader } from '../../ui/PageHeader'
import { INVENTAIRE_ACCENT } from '../../features/stock/inventaireAccent'

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

// ── Modal de consultation d'un retour ───────────────────────────────────────
// XPUR9 / WIR222 — un retour VALIDÉ peut générer son avoir fournisseur ; le
// serveur refuse (400) un second appel, ce qui préserve la garde
// anti-double-avoir. Export nommé : testé directement.
export function RetourDetail({ retour, onClose, onAvoirGenere }) {
  const lignes = retour?.lignes ?? []
  const [busy, setBusy] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [avoir, setAvoir] = useState(null)

  const genererAvoir = async () => {
    setBusy(true); setErreur(null)
    try {
      const r = await stockApi.genererAvoirRetourFournisseur(retour.id)
      setAvoir(r.data ?? {})
      onAvoirGenere?.()
    } catch (err) {
      const d = err?.response?.data
      // 400 serveur affiché TEL QUEL (retour non validé / avoir déjà émis).
      setErreur((typeof d === 'string' ? d : d?.detail)
        || "La génération de l'avoir a échoué.")
    } finally { setBusy(false) }
  }

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

        {erreur && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {erreur}
          </div>
        )}
        {avoir && (
          <div className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
            Avoir {avoir.reference ?? ''} généré (brouillon) — montant
            {' '}{avoir.montant_ttc ?? avoir.montant_ht ?? '—'}.
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
          {/* XPUR9 / WIR222 — l'avoir n'a de sens que sur un retour VALIDÉ ;
              un second clic est refusé côté serveur (garde anti-doublon). */}
          {retour.statut === 'valide' && (
            <Button type="button" loading={busy} onClick={genererAvoir}>
              {busy ? '…' : "Générer l'avoir"}
            </Button>
          )}
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

  const reload = () => {
    stockApi.getRetoursFournisseur({ ordering: '-date_creation' })
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des retours impossible.'))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { reload() }, [])

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
      <PageHeader
        style={{ '--module-accent': INVENTAIRE_ACCENT }}
        className="app-accent-rail mb-0"
        headingAs="h1"
        icon={Undo2}
        title="Retours fournisseur"
        subtitle={`${items.length} retour(s)`}
      />

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
        <RetourDetail retour={selected} onClose={() => setSelected(null)}
                      onAvoirGenere={reload} />
      )}
    </div>
  )
}
