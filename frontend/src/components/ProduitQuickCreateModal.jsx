import { useEffect, useState } from 'react'
import stockApi from '../api/stockApi'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button, Input, Label, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../ui'

const CATEGORIE_AUCUNE = '__aucune'

/* QG6 — « + Nouveau produit » quick-create partagé (devis + BCF).
   Minimal : nom + prix de vente HT (+ prix d'achat optionnel, INTERNE — jamais
   client-facing). Appelle stockApi.createProduit (company forcée côté serveur,
   apps/stock/views/produit.py) puis rappelle onCreated(produit) pour que
   l'appelant sélectionne le nouveau produit sur sa ligne. Le bouton qui ouvre
   cette modale est déjà gardé par le hook QG5 (Directeur + Commercial
   responsable) côté appelant — cette modale ne fait qu'exécuter la création,
   le serveur (QG4 HasPermissionAndRole) reste la seule garde qui compte.

   STKCAT13 — Catégorie TOUJOURS visible, JAMAIS requise (fiche minimale
   toujours créable sans catégorie ; « ranger plus tard » reste un choix
   honnête). `categories` (optionnel) permet à l'appelant (ProduitPicker, qui
   les a déjà chargées pour calculer `defaultCategorieId`) d'éviter un second
   appel réseau ; sans cette prop la modale charge la liste elle-même à
   l'ouverture (silencieux si l'appel échoue — liste vide, jamais un blocage
   de la création). `defaultCategorieId` pré-sélectionne la catégorie SEULEMENT
   quand l'appelant l'a résolue sans ambiguïté (ex. ProduitPicker : la famille
   de la ligne désigne EXACTEMENT une catégorie typée de la société). */
export default function ProduitQuickCreateModal({
  open, onClose, onCreated, categories, defaultCategorieId,
}) {
  const [nom, setNom] = useState('')
  const [prixVente, setPrixVente] = useState('')
  const [prixAchat, setPrixAchat] = useState('')
  // STKCAT13 — `null` = l'utilisateur n'a pas encore touché le select : on
  // suit alors `defaultCategorieId` (déduit par l'appelant, peut changer
  // d'une ouverture à l'autre puisque la modale reste montée entre deux
  // lignes). Dérivé au RENDU (jamais un effet + setState en cascade) — un
  // choix explicite (même « Aucune », override = '') prime toujours dessus.
  const [categorieOverride, setCategorieOverride] = useState(null)
  const categorieId = categorieOverride ?? (defaultCategorieId ? String(defaultCategorieId) : '')
  const [categoriesFetched, setCategoriesFetched] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // Chargement paresseux, UNIQUEMENT si l'appelant n'a pas déjà la liste —
  // échec silencieux (liste vide) : jamais une création bloquée par ça.
  useEffect(() => {
    if (!open || categories) return
    let cancelled = false
    stockApi.getCategories({ page_size: 200 })
      .then((r) => { if (!cancelled) setCategoriesFetched(r.data?.results ?? r.data ?? []) })
      .catch(() => { if (!cancelled) setCategoriesFetched([]) })
    return () => { cancelled = true }
  }, [open, categories])

  const categoriesOptions = categories ?? categoriesFetched

  const reset = () => {
    setNom(''); setPrixVente(''); setPrixAchat(''); setCategorieOverride(null); setError(null)
  }

  const handleClose = () => { reset(); onClose?.() }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!nom.trim()) { setError('Le nom du produit est requis.'); return }
    setBusy(true)
    try {
      const payload = {
        nom: nom.trim(),
        prix_vente: prixVente !== '' ? prixVente : '0',
        prix_achat: prixAchat !== '' ? prixAchat : '0',
      }
      if (categorieId) payload.categorie_id = Number(categorieId)
      const res = await stockApi.createProduit(payload)
      onCreated?.(res.data)
      reset()
    } catch (err) {
      const data = err?.response?.data
      const detail = typeof data?.detail === 'string'
        ? data.detail
        : (data && typeof data === 'object'
          ? Object.values(data).flat().filter(Boolean)[0]
          : null)
      setError(typeof detail === 'string' ? detail : 'La création du produit a échoué.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nouveau produit</DialogTitle>
          <DialogDescription>
            Création rapide — vous pourrez compléter la fiche complète
            (marque, garantie…) plus tard depuis Stock.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} noValidate className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="pqc-nom" required>Nom du produit</Label>
            <Input id="pqc-nom" value={nom} autoFocus
                   invalid={error && !nom.trim() ? true : undefined}
                   onChange={(e) => setNom(e.target.value)}
                   placeholder="ex : Onduleur Huawei SUN2000 10KTL" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="pqc-categorie">Catégorie</Label>
            <Select
              value={categorieId || CATEGORIE_AUCUNE}
              onValueChange={(v) => setCategorieOverride(v === CATEGORIE_AUCUNE ? '' : v)}
            >
              <SelectTrigger id="pqc-categorie">
                <SelectValue placeholder="Aucune (à ranger plus tard)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={CATEGORIE_AUCUNE}>Aucune (à ranger plus tard)</SelectItem>
                {categoriesOptions.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="pqc-vente">Prix de vente HT</Label>
              <Input id="pqc-vente" type="number" min="0" step="any"
                     value={prixVente} onChange={(e) => setPrixVente(e.target.value)}
                     placeholder="0" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="pqc-achat">Prix d'achat HT (interne)</Label>
              <Input id="pqc-achat" type="number" min="0" step="any"
                     value={prixAchat} onChange={(e) => setPrixAchat(e.target.value)}
                     placeholder="0" />
            </div>
          </div>
          {error && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={handleClose} disabled={busy}>
              Annuler
            </Button>
            <Button type="submit" loading={busy}>
              {busy ? 'Création…' : 'Créer et sélectionner'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
