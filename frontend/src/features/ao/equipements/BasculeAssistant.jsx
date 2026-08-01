import { useMemo, useState } from 'react'
import { AlertTriangle, ArrowRightLeft, Search } from 'lucide-react'
import stockApi from '../../../api/stockApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import {
  Badge, Button, Input, Skeleton, Textarea,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'

/* ============================================================================
   AOF180 — Assistant de bascule d'équipement (ancien → nouveau).
   ----------------------------------------------------------------------------
   AOF141 fait de la bascule une OPÉRATION ATOMIQUE nommée (désignation, prix,
   grandeurs dérivées recalculées, lignes de bordereau, fiche annexée ajoutée
   ET ancienne retirée — 23 remplacements cohérents sur le cas réel batterie
   BOS-G → BOS-B Pro-A3). C'est l'opération la PLUS RISQUÉE du dossier : sans
   cet écran, elle resterait un appel d'API.

   **Trois clics, motif OBLIGATOIRE** : « Basculer » (dans la liste) → choisir
   le nouveau matériel dans le catalogue → « Confirmer la bascule ». Le motif
   est saisi et jamais facultatif — une bascule sans motif est un dossier dont
   personne ne saura, dans six mois, pourquoi il a changé de batterie.

   **AUCUN COÛT NE SORT D'ICI** (en-tête du Groupe AOF : l'économie est
   réservée au directeur). Le catalogue est affiché SANS `prix_achat`, sans
   marge et sans coût de revient, et le corps de la requête est construit par
   une ALLOWLIST explicite (`payloadBascule`) — jamais par diffusion d'un objet
   produit, qui embarquerait `prix_achat` sans que personne le voie.
   ========================================================================== */

/** Corps de la requête de bascule — allowlist STRICTE. Toute clé absente de
    cette fonction ne peut pas partir sur le réseau. */
export function payloadBascule({ produitId, motif, quantite }) {
  const corps = { nouveau_produit: produitId, motif: String(motif ?? '').trim() }
  if (quantite != null && quantite !== '') corps.quantite = quantite
  return corps
}

function CatalogueItem({ produit, onChoisir }) {
  const sansPrix = produit.prix_vente == null || produit.prix_vente === ''
  return (
    <li>
      <button
        type="button"
        onClick={() => onChoisir(produit)}
        className="flex w-full flex-col items-start gap-0.5 rounded-md border border-border p-2 text-left hover:bg-accent focus-ring"
      >
        <span className="text-sm font-medium">{produit.nom}</span>
        <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          {produit.marque || '—'}
          {produit.reference ? ` · réf. ${produit.reference}` : ''}
          {produit.is_archived && <Badge tone="warning">archivé</Badge>}
          {sansPrix && <Badge tone="warning">prix à renseigner</Badge>}
        </span>
      </button>
    </li>
  )
}

export default function BasculeAssistant({ equipement, onFermer, onBasculer }) {
  const [recherche, setRecherche] = useState('')
  const [nouveau, setNouveau] = useState(null)
  const [motif, setMotif] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState(null)

  const params = useMemo(() => ({ search: recherche }), [recherche])
  const { data: produits, loading } = useResource(
    (p) => stockApi.getProduits(p), params,
    { initialData: [], select: unwrapList, errorMessage: () => '' },
  )

  const motifOk = motif.trim().length > 0

  const confirmer = async () => {
    if (!nouveau || !motifOk) return
    setEnvoi(true)
    setErreur(null)
    try {
      await onBasculer(equipement, payloadBascule({ produitId: nouveau.id, motif }))
      onFermer()
    } catch (e) {
      setErreur(e?.response?.data?.detail || 'Bascule refusée — le dossier est inchangé.')
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onFermer() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Basculer « {equipement.designation || equipement.produit_designation} »
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <p className="flex items-start gap-1.5 rounded-md border border-warning/40 bg-warning/5 p-2.5 text-xs text-warning">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            Opération ATOMIQUE : désignation, grandeurs dérivées, lignes de bordereau et fiche
            technique annexée sont mises à jour ensemble, ou pas du tout.
          </p>

          {!nouveau ? (
            <>
              <div className="flex items-center gap-2">
                <Search className="size-4 text-muted-foreground" aria-hidden="true" />
                <Input
                  aria-label="Rechercher un matériel dans le catalogue"
                  placeholder="Référence, marque, désignation…"
                  value={recherche}
                  onChange={(e) => setRecherche(e.target.value)}
                />
              </div>
              {loading ? (
                <Skeleton className="h-24 w-full" />
              ) : (
                <ul className="flex max-h-64 flex-col gap-1.5 overflow-y-auto">
                  {produits.map((p) => (
                    <CatalogueItem key={p.id} produit={p} onChoisir={setNouveau} />
                  ))}
                </ul>
              )}
            </>
          ) : (
            <>
              <p className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-muted-foreground">
                  {equipement.designation || equipement.produit_designation}
                </span>
                <ArrowRightLeft className="size-4" aria-hidden="true" />
                <span className="font-medium">{nouveau.nom}</span>
                <Button size="sm" variant="link" onClick={() => setNouveau(null)}>Changer</Button>
              </p>
              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium" htmlFor="ao-bascule-motif">
                  Motif de la bascule <span aria-hidden="true" className="text-destructive">*</span>
                </label>
                <Textarea
                  id="ao-bascule-motif"
                  rows={3}
                  value={motif}
                  onChange={(e) => setMotif(e.target.value)}
                  placeholder="Ex. batterie BOS-G indisponible — remplacée par BOS-B Pro-A3."
                />
              </div>
              {erreur && <p className="text-xs text-destructive">{erreur}</p>}
            </>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onFermer}>Annuler</Button>
          <Button type="button" disabled={!nouveau || !motifOk || envoi} onClick={confirmer}>
            {envoi ? 'Bascule…' : 'Confirmer la bascule'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
