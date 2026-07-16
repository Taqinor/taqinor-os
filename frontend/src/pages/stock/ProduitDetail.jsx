import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { History, PackageSearch } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { useHasPermission } from '../../hooks/useHasPermission'
import {
  Spinner, Badge, RelationCounters,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button, Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'

// ZPUR10 / ZSTK3 — Fiche produit (au-delà du catalogue) : quantité « en
// commande » (BCF brouillon/envoyé, jamais annulé/reçu) + rapport
// prévisionnel (disponible + entrées/sorties attendues → solde projeté
// daté). Donnée INTERNE (prix d'achat jamais client-facing) — la fiche ne
// modifie jamais aucun stock/mouvement, lecture seule.

const fmtDateFR = (iso) => {
  if (!iso) return 'Date inconnue'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? 'Date inconnue' : d.toLocaleDateString('fr-FR')
}

function Chargement() {
  return (
    <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner /> Chargement…
    </div>
  )
}

// ── Onglet « En commande » — BCF sources contribuant à la quantité engagée ──
function OngletEnCommande({ produit }) {
  const enCommande = produit.quantite_en_commande ?? 0
  const sources = produit.bcf_sources_en_commande ?? []
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-border bg-muted/30 p-3">
        <p className="text-xs text-muted-foreground">Quantité en commande</p>
        <p className="mt-1 text-lg font-semibold tabular-nums">{enCommande}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Somme des restants sur les BCF brouillon/envoyé (jamais annulé/reçu).
        </p>
      </div>
      {sources.length === 0 ? (
        <p className="py-2 text-sm text-muted-foreground">Aucun bon de commande ouvert pour ce produit.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[28rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Bon de commande</th>
                <th className="px-3 py-2 text-left font-semibold">Fournisseur</th>
                <th className="px-3 py-2 text-left font-semibold">Livraison prévue</th>
                <th className="px-3 py-2 text-right font-semibold">Reste à recevoir</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.bon_commande_id} className="border-t border-border">
                  <td className="px-3 py-2 font-mono text-xs">{s.reference}</td>
                  <td className="px-3 py-2">{s.fournisseur_nom ?? <span className="text-muted-foreground">—</span>}</td>
                  <td className="px-3 py-2">{fmtDateFR(s.date_livraison_prevue)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.quantite_restante}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Onglet « Prévisionnel » — solde projeté daté (ZSTK3) ────────────────────
function OngletPrevisionnel({ produitId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.produitPrevisionnel(produitId)
      .then((r) => { if (active) setData(r.data ?? null) })
      .catch(() => { if (active) setError('Rapport prévisionnel indisponible.') })
    return () => { active = false }
  }, [produitId])

  if (error) return <p className="py-3 text-sm text-muted-foreground">{error}</p>
  if (!data) return <Chargement />

  const timeline = data.timeline ?? []

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-xs text-muted-foreground">Disponible</p>
          <p className="mt-1 text-lg font-semibold tabular-nums">{data.disponible}</p>
        </div>
        <div className="rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-xs text-muted-foreground">Sorties attendues</p>
          <p className="mt-1 text-lg font-semibold tabular-nums">{data.sorties_attendues ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-xs text-muted-foreground">Solde projeté</p>
          <p className="mt-1 text-lg font-semibold tabular-nums">{data.solde_projete}</p>
        </div>
      </div>
      {timeline.length === 0 ? (
        <p className="py-2 text-sm text-muted-foreground">Aucun mouvement attendu.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[28rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Date</th>
                <th className="px-3 py-2 text-left font-semibold">Type</th>
                <th className="px-3 py-2 text-left font-semibold">Référence</th>
                <th className="px-3 py-2 text-right font-semibold">Quantité</th>
                <th className="px-3 py-2 text-right font-semibold">Solde projeté</th>
              </tr>
            </thead>
            <tbody>
              {timeline.map((t, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="px-3 py-2">{fmtDateFR(t.date)}</td>
                  <td className="px-3 py-2">
                    <Badge tone={t.type === 'entree' ? 'success' : 'warning'}>
                      {t.type === 'entree' ? 'Entrée attendue' : 'Sortie réservée'}
                    </Badge>
                  </td>
                  <td className="px-3 py-2">
                    {t.reference
                      ? <span className="font-mono text-xs">{t.reference}{t.fournisseur_nom ? ` · ${t.fournisseur_nom}` : ''}</span>
                      : <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    <span className={t.quantite >= 0 ? 'text-success' : 'text-destructive'}>
                      {t.quantite >= 0 ? '+' : ''}{t.quantite}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right font-semibold tabular-nums">{t.solde_projete}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// Export nommé : testé directement.
export function ProduitDetail({ produit, onClose }) {
  // VX98 — bouton « Historique » → Journal pré-filtré sur CE produit, visible
  // uniquement avec la permission journal_activite_voir (AuditLog couvre tous
  // les modèles ; le backend re-vérifie la permission).
  const canViewJournal = useHasPermission('journal_activite_voir')
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <PackageSearch className="size-4 text-muted-foreground" aria-hidden="true" />
            {produit.nom}{produit.sku ? ` (${produit.sku})` : ''}
          </DialogTitle>
          <DialogDescription>
            Engagements d&apos;achat et rapport prévisionnel — donnée interne, lecture seule.
          </DialogDescription>
        </DialogHeader>

        {/* VX159/VX250 — RelationCounters : réutilise `produit.bcf_sources_en_commande`
            déjà chargé (prop, ZÉRO appel réseau nouveau). Pas de filtre par
            produit sur BonsCommandeFournisseur.jsx (hors périmètre de cette
            tâche) : lien vers la liste NUE, jamais un pré-filtre qui MENT.
            `prix_achat` ne transite jamais par ce composant (label/count
            purement quantitatifs). */}
        <RelationCounters
          className="mb-3"
          counters={[{
            label: 'bons de commande en cours',
            count: produit.bcf_sources_en_commande?.length ?? 0,
            to: '/stock/bons-commande-fournisseur',
          }]}
        />

        <Tabs defaultValue="en-commande">
          <TabsList>
            <TabsTrigger value="en-commande">En commande</TabsTrigger>
            <TabsTrigger value="previsionnel">Prévisionnel</TabsTrigger>
          </TabsList>
          <TabsContent value="en-commande">
            <OngletEnCommande produit={produit} />
          </TabsContent>
          <TabsContent value="previsionnel">
            <OngletPrevisionnel produitId={produit.id} />
          </TabsContent>
        </Tabs>

        <DialogFooter>
          {canViewJournal && (
            <Button asChild type="button" variant="outline">
              <Link to={`/journal?model=produit&object_id=${produit.id}`}>
                <History className="size-4" aria-hidden="true" /> Historique
              </Link>
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default ProduitDetail
