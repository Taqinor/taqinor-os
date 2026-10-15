// NTUX10 — « + Nouveau ticket SAV » quick-create universel (palette ⌘K).
// Minimal : client + type + description. WIR178 — `client` est un FK NON
// NULLABLE côté serveur (apps/sav/models.py `Ticket.client`) : un payload
// sans client était un 400 garanti, jamais une complétion différée. Le
// sélecteur Client est donc OBLIGATOIRE ici, pas optionnel. Appelle
// savApi.createTicket (company forcée côté serveur) puis rappelle
// onCreated(ticket).
import { useState } from 'react'
import savApi from '../../../api/savApi'
import { TICKET_TYPES } from '../../sav/ticketStatuses'
import {
  Label, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import { frErrRapide } from '../../../lib/frErr'
import ModaleCreationRapide from '../../../components/ModaleCreationRapide'
import ComboboxClient from '../../../components/ComboboxClient'

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
      setError(frErrRapide(err, 'La création du ticket a échoué.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <ModaleCreationRapide open={open} onFermer={handleClose} onSubmit={handleSubmit}
      titre="Nouveau ticket SAV"
      description={<>
        Création rapide — vous pourrez rattacher l'installation et compléter
        la fiche plus tard depuis SAV.
      </>}
      error={error} busy={busy} libelle="Créer" libelleEnCours="Création…">
      <div className="grid gap-1.5">
        <Label htmlFor="tqc-client" required>Client</Label>
        <ComboboxClient id="tqc-client" value={clientId} onChange={(v) => setClientId(v)}
                        invalid={error && !clientId ? true : undefined} />
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
    </ModaleCreationRapide>
  )
}
