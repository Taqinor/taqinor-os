// NTFSM20 — onglet « Mon stock camionnette » de /ma-journee (F22).
//
// Le technicien voit UNIQUEMENT le stock de SA propre camionnette — jamais
// celui d'un collègue : l'emplacement est résolu CÔTÉ SERVEUR (chaîne
// flotte : utilisateur → conducteur → affectation véhicule active →
// emplacement de stock lié), jamais accepté depuis ce composant. Sans
// camionnette affectée, un état vide propre s'affiche (pas une erreur).
//
// Le bouton « Signaler manquant » crée une demande de transfert dépôt
// principal → camionnette (NTFSM19) SANS attendre le job de réappro
// automatique.
import { useCallback, useEffect, useState } from 'react'
import { PackageSearch, AlertTriangle } from 'lucide-react'
import stockApi from '../../api/stockApi'
import {
  Spinner, EmptyState, Badge, Button, toast,
} from '../../ui'

export default function MonStockCamionnetteTab() {
  const [loading, setLoading] = useState(true)
  const [emplacement, setEmplacement] = useState(null)
  const [produits, setProduits] = useState([])
  const [signalingId, setSignalingId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    return stockApi.getMonStockCamionnette()
      .then((r) => {
        setEmplacement(r.data?.emplacement ?? null)
        setProduits(r.data?.produits ?? [])
      })
      .catch(() => {
        setEmplacement(null)
        setProduits([])
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const signalerManquant = (produitId) => {
    setSignalingId(produitId)
    stockApi.signalerManquantVanStock(produitId)
      .then(() => {
        toast.success('Manque signalé — une demande de transfert a été créée.')
      })
      .catch((err) => {
        toast.error(err?.response?.data?.detail || 'Le signalement a échoué.')
      })
      .finally(() => setSignalingId(null))
  }

  if (loading) {
    return (
      <p className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
        <Spinner className="size-4" /> Chargement de votre stock…
      </p>
    )
  }

  if (!emplacement) {
    return (
      <EmptyState
        icon={PackageSearch}
        title="Aucune camionnette affectée"
        description="Aucun véhicule de stock ne vous est actuellement affecté." />
    )
  }

  if (produits.length === 0) {
    return (
      <EmptyState
        icon={PackageSearch}
        title={`${emplacement.nom} — aucun produit suivi`}
        description="Aucun produit n'est encore suivi sur cette camionnette." />
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="text-sm font-medium text-muted-foreground">
        {emplacement.nom}
      </div>
      <ol className="flex flex-col gap-2">
        {produits.map((p) => {
          const sousLeSeuil = p.seuil_min != null && p.quantite < p.seuil_min
          return (
            <li key={p.produit_id}
              className="flex items-center gap-3 rounded-lg border p-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium">{p.nom}</span>
                  {sousLeSeuil && (
                    <Badge tone="danger" className="gap-1">
                      <AlertTriangle className="size-3" aria-hidden="true" />
                      Sous seuil
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {p.sku ? `${p.sku} · ` : ''}Quantité : {p.quantite}
                  {p.seuil_min != null ? ` (seuil min ${p.seuil_min})` : ''}
                </div>
              </div>
              <Button
                type="button" size="sm" variant="outline"
                disabled={signalingId === p.produit_id}
                onClick={() => signalerManquant(p.produit_id)}>
                {signalingId === p.produit_id ? 'Envoi…' : 'Signaler manquant'}
              </Button>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
