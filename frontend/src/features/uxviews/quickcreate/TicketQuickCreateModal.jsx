// NTUX10 — « + Nouveau ticket SAV » quick-create universel (palette ⌘K).
// WIR178 — `client` est un FK REQUIS côté serveur (`apps/sav/models.py`,
// aucun `null=True`) : le payload minimal type+description ci-dessous
// renvoyait un 400 garanti à CHAQUE création. Un sélecteur Client obligatoire
// est maintenant posé (`installation` reste optionnel, complétion différée
// depuis l'écran SAV complet). Appelle savApi.createTicket (company forcée
// côté serveur) puis rappelle onCreated(ticket).
import { useEffect, useState } from 'react'
import savApi from '../../../api/savApi'
import crmApi from '../../../api/crmApi'
import { TICKET_TYPES } from '../../sav/ticketStatuses'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button, Label, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'

export default function TicketQuickCreateModal({ open, onClose, onCreated }) {
  const [type, setType] = useState(TICKET_TYPES[0]?.value ?? 'correctif')
  const [description, setDescription] = useState('')
  const [clientId, setClientId] = useState('')
  const [clients, setClients] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!open) return
    crmApi.getClients().then((r) => setClients(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [open])

  const reset = () => {
    setType(TICKET_TYPES[0]?.value ?? 'correctif'); setDescription(''); setClientId(''); setError(null)
  }
  const handleClose = () => { reset(); onClose?.() }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!clientId) { setError('Le client est requis.'); return }
    if (!description.trim()) { setError('La description est requise.'); return }
    setBusy(true)
    try {
      const res = await savApi.createTicket({ type, client: clientId, description: description.trim() })
      onCreated?.(res.data)
      reset()
    } catch (err) {
      const data = err?.response?.data
      const detail = typeof data?.detail === 'string'
        ? data.detail
        : (data && typeof data === 'object'
          ? Object.values(data).flat().filter(Boolean)[0]
          : null)
      setError(typeof detail === 'string' ? detail : 'La création du ticket a échoué.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nouveau ticket SAV</DialogTitle>
          <DialogDescription>
            Création rapide — le chantier (installation) reste optionnel, complétez la
            fiche plus tard depuis SAV.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} noValidate className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="tqc-client" required>Client</Label>
            <Select value={clientId} onValueChange={setClientId}>
              <SelectTrigger id="tqc-client" aria-label="Client"><SelectValue placeholder="— Client —" /></SelectTrigger>
              <SelectContent>
                {clients.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.nom} {c.prenom || ''}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="tqc-type">Type</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger id="tqc-type" autoFocus><SelectValue /></SelectTrigger>
              <SelectContent>
                {TICKET_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="tqc-description" required>Description</Label>
            <Textarea
              id="tqc-description" rows={3} value={description}
              invalid={error && !description.trim() ? true : undefined}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Décrivez le problème signalé…"
            />
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
              {busy ? 'Création…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
