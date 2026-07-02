import { useState } from 'react'
import crmApi from '../../api/crmApi'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button, Input, Label,
} from '../../ui'

/* QG3 — « + Nouveau client » quick-create depuis le générateur de devis
   (chemin sans lead). Minimal : nom + téléphone/email — appelle
   crmApi.createClient (company forcée côté serveur, apps/crm/views.py
   perform_create) puis rappelle onCreated(client) pour que l'appelant
   sélectionne automatiquement le nouveau client. */
export default function ClientQuickCreateModal({ open, onClose, onCreated }) {
  const [nom, setNom] = useState('')
  const [prenom, setPrenom] = useState('')
  const [telephone, setTelephone] = useState('')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const reset = () => {
    setNom(''); setPrenom(''); setTelephone(''); setEmail(''); setError(null)
  }
  const handleClose = () => { reset(); onClose?.() }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!nom.trim()) { setError('Le nom est requis.'); return }
    setBusy(true)
    try {
      const payload = {
        nom: nom.trim(),
        prenom: prenom.trim() || null,
        telephone: telephone.trim() || null,
        email: email.trim() || null,
      }
      const res = await crmApi.createClient(payload)
      onCreated?.(res.data)
      reset()
    } catch (err) {
      const data = err?.response?.data
      const detail = typeof data?.detail === 'string'
        ? data.detail
        : (data && typeof data === 'object'
          ? Object.values(data).flat().filter(Boolean)[0]
          : null)
      setError(typeof detail === 'string' ? detail : 'La création du client a échoué.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nouveau client</DialogTitle>
          <DialogDescription>
            Création rapide — vous pourrez compléter la fiche complète (ICE, adresse…)
            plus tard depuis Clients.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} noValidate className="grid gap-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="cqc-nom" required>Nom</Label>
              <Input id="cqc-nom" value={nom} autoFocus
                     invalid={error && !nom.trim() ? true : undefined}
                     onChange={(e) => setNom(e.target.value)}
                     placeholder="Dupont" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="cqc-prenom">Prénom</Label>
              <Input id="cqc-prenom" value={prenom}
                     onChange={(e) => setPrenom(e.target.value)}
                     placeholder="Jean" />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="cqc-tel">Téléphone</Label>
            <Input id="cqc-tel" type="tel" value={telephone}
                   onChange={(e) => setTelephone(e.target.value)}
                   placeholder="+212 6 XX XX XX XX" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="cqc-email">Email</Label>
            <Input id="cqc-email" type="email" value={email}
                   onChange={(e) => setEmail(e.target.value)}
                   placeholder="jean.dupont@exemple.com" />
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
