// NTUX10 — « + Nouveau ticket SAV » quick-create universel (palette ⌘K).
// Minimal : client + type + description. WIR178 — `client` est un FK NON
// NULLABLE côté serveur (apps/sav/models.py `Ticket.client`) : un payload
// sans client était un 400 garanti, jamais une complétion différée. Le
// sélecteur Client est donc OBLIGATOIRE ici, pas optionnel. Appelle
// savApi.createTicket (company forcée côté serveur) puis rappelle
// onCreated(ticket).
import { useState } from 'react'
import savApi from '../../../api/savApi'
import crmApi from '../../../api/crmApi'
import { searchCompanies } from '../../crm/companyLookup'
import { TICKET_TYPES } from '../../sav/ticketStatuses'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button, Label, Textarea, Combobox,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'

export default function TicketQuickCreateModal({ open, onClose, onCreated }) {
  const [clientId, setClientId] = useState(null)
  const [type, setType] = useState(TICKET_TYPES[0]?.value ?? 'correctif')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const reset = () => {
    setClientId(null)
    setType(TICKET_TYPES[0]?.value ?? 'correctif'); setDescription(''); setError(null)
  }
  const handleClose = () => { reset(); onClose?.() }

  // WIR178 — mêmes données propres que DevisGenerator (endpoint /search/,
  // filtré aux clients : un ticket a besoin d'un id client réel).
  const onSearchClient = async (query) => {
    const hits = await searchCompanies(query, { searcher: crmApi.searchClients })
    const clientHits = hits.filter((h) => h.source === 'client')
    return clientHits.map((h) => ({ value: String(h.id), label: h.nom }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!clientId) { setError('Le client est requis.'); return }
    if (!description.trim()) { setError('La description est requise.'); return }
    setBusy(true)
    try {
      const res = await savApi.createTicket({
        client: parseInt(clientId, 10), type, description: description.trim(),
      })
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
            Création rapide — vous pourrez rattacher l'installation et compléter
            la fiche plus tard depuis SAV.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} noValidate className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="tqc-client" required>Client</Label>
            <Combobox
              id="tqc-client"
              autoFocus
              value={clientId}
              onChange={(v) => setClientId(v)}
              onSearch={onSearchClient}
              placeholder="— Sélectionner un client —"
              searchPlaceholder="Nom ou ICE…"
              emptyText="Aucun client dans vos données"
              invalid={error && !clientId ? true : undefined}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="tqc-type">Type</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger id="tqc-type"><SelectValue /></SelectTrigger>
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
