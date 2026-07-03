import { useState } from 'react'
import stockApi from '../api/stockApi'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button, Input, Label,
} from '../ui'

/* QG6 — « + Nouveau produit » quick-create partagé (devis + BCF).
   Minimal : nom + prix de vente HT (+ prix d'achat optionnel, INTERNE — jamais
   client-facing). Appelle stockApi.createProduit (company forcée côté serveur,
   apps/stock/views/produit.py) puis rappelle onCreated(produit) pour que
   l'appelant sélectionne le nouveau produit sur sa ligne. Le bouton qui ouvre
   cette modale est déjà gardé par le hook QG5 (Directeur + Commercial
   responsable) côté appelant — cette modale ne fait qu'exécuter la création,
   le serveur (QG4 HasPermissionAndRole) reste la seule garde qui compte. */
export default function ProduitQuickCreateModal({ open, onClose, onCreated }) {
  const [nom, setNom] = useState('')
  const [prixVente, setPrixVente] = useState('')
  const [prixAchat, setPrixAchat] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const reset = () => {
    setNom(''); setPrixVente(''); setPrixAchat(''); setError(null)
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
            Création rapide — vous pourrez compléter la fiche complète (catégorie,
            marque, garantie…) plus tard depuis Stock.
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
