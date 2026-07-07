import { useEffect, useMemo, useState } from 'react'
import posApi from '../../api/posApi'
import {
  Button, Input, Label, Badge, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  toast,
} from '../../ui'

/* XPOS15 — File click-and-collect (route /pos/retraits).
   Workflow : à préparer → prêt → retiré. « Marquer prêt » décrémente le stock
   (backend) ; « Remettre » vérifie le code de retrait du client. */
const STATUT_LABEL = {
  a_preparer: 'À préparer',
  pret: 'Prêt au retrait',
  retire: 'Retiré',
  annule: 'Annulé',
}
const STATUT_TONE = {
  a_preparer: 'warning',
  pret: 'info',
  retire: 'success',
  annule: 'neutral',
}

export default function RetraitsScreen() {
  const [retraits, setRetraits] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  // Remise : dialogue de vérification du code de retrait.
  const [remiseOpen, setRemiseOpen] = useState(false)
  const [commande, setCommande] = useState(null)
  const [code, setCode] = useState('')

  const load = () => {
    return posApi.getRetraits()
      .then((r) => {
        const data = r?.data?.results ?? r?.data ?? []
        setRetraits(Array.isArray(data) ? data : [])
      })
      .catch(() => setRetraits([]))
      .finally(() => setLoading(false))
  }
  const charger = () => { setLoading(true); return load() }

  useEffect(() => { load() }, [])

  const enAttente = useMemo(
    () => retraits.filter((c) => c.statut === 'a_preparer' || c.statut === 'pret'),
    [retraits])

  const handleMarquerPret = async (c) => {
    setBusy(true)
    try {
      await posApi.marquerPret(c.id)
      toast.success('Commande prête au retrait.')
      await charger()
    } catch {
      toast.error('Impossible de marquer prête (stock insuffisant ?).')
    } finally {
      setBusy(false)
    }
  }

  const ouvrirRemise = (c) => {
    setCommande(c)
    setCode('')
    setRemiseOpen(true)
  }

  const handleRemettre = async () => {
    if (!commande) return
    setBusy(true)
    try {
      await posApi.remettreRetrait(commande.id, { code: code.trim() })
      toast.success('Commande remise au client.')
      setRemiseOpen(false)
      setCommande(null)
      await charger()
    } catch {
      toast.error('Code de retrait invalide ou commande non prête.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-display text-xl font-semibold">Retraits en magasin</h1>
        <span className="text-sm text-muted-foreground">{enAttente.length} en attente</span>
      </div>

      {loading ? (
        <div className="py-8 text-center text-sm text-muted-foreground">Chargement…</div>
      ) : retraits.length === 0 ? (
        <EmptyState title="Aucune commande" description="Les commandes à retirer apparaîtront ici." />
      ) : (
        <ul className="flex flex-col gap-2" data-testid="retraits-liste">
          {retraits.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card p-3">
              <div className="flex flex-col gap-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{c.reference}</span>
                  <Badge tone={STATUT_TONE[c.statut] || 'neutral'}>
                    {STATUT_LABEL[c.statut] || c.statut}
                  </Badge>
                </div>
                <span className="text-xs text-muted-foreground">
                  {c.client_nom || `Client #${c.client}`}
                  {' · '}{(c.lignes || []).length} article(s)
                </span>
              </div>
              <div className="flex gap-2">
                {c.statut === 'a_preparer' && (
                  <Button type="button" size="sm" onClick={() => handleMarquerPret(c)} disabled={busy}>
                    Marquer prêt
                  </Button>
                )}
                {c.statut === 'pret' && (
                  <Button type="button" size="sm" onClick={() => ouvrirRemise(c)} disabled={busy}>
                    Remettre
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Remise au client — vérification du code de retrait */}
      <Dialog open={remiseOpen} onOpenChange={(o) => { if (!o) setRemiseOpen(false) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Remettre la commande {commande?.reference}</DialogTitle>
            <DialogDescription>Saisissez le code de retrait communiqué au client.</DialogDescription>
          </DialogHeader>
          <form noValidate onSubmit={(e) => { e.preventDefault(); handleRemettre() }} className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="retrait-code" required>Code de retrait</Label>
              <Input id="retrait-code" autoFocus value={code}
                     onChange={(e) => setCode(e.target.value)} placeholder="Ex. A1B2C3" />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setRemiseOpen(false)}>Annuler</Button>
              <Button type="submit" loading={busy}>Confirmer la remise</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
