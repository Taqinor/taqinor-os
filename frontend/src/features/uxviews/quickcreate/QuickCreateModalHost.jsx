// NTUX10 — Hôte unique du quick-create universel : écoute l'événement
// `taqinor:quick-create` (émis par la palette de commandes, ⌘K → « Créer… »)
// et monte le modal correspondant PAR-DESSUS l'écran courant, sans aucune
// navigation. Monté UNE FOIS près de la racine (router/index.jsx, à côté de
// `<CommandPalette />`) — indépendant du cycle de vie de la palette (fermer
// la palette ne démonte pas ce modal).
import { useEffect, useState } from 'react'
import LeadExpressModal from '../../../pages/crm/leads/LeadExpressModal'
import ClientQuickCreateModal from '../../../pages/ventes/ClientQuickCreateModal'
import ProduitQuickCreateModal from '../../../components/ProduitQuickCreateModal'
import TicketQuickCreateModal from './TicketQuickCreateModal'
import { toast } from '../../../ui/confirm'
import { QUICK_CREATE_EVENT } from './quickCreateEvents'

export default function QuickCreateModalHost() {
  const [type, setType] = useState(null)

  useEffect(() => {
    const onEvent = (e) => setType(e.detail?.type || null)
    window.addEventListener(QUICK_CREATE_EVENT, onEvent)
    return () => window.removeEventListener(QUICK_CREATE_EVENT, onEvent)
  }, [])

  const close = () => setType(null)

  if (type === 'lead') {
    return (
      <LeadExpressModal
        onClose={close}
        onSaved={() => { toast.success('Lead créé.'); close() }}
      />
    )
  }
  if (type === 'client') {
    return (
      <ClientQuickCreateModal
        open onClose={close}
        onCreated={() => { toast.success('Client créé.'); close() }}
      />
    )
  }
  if (type === 'produit') {
    return (
      <ProduitQuickCreateModal
        open onClose={close}
        onCreated={() => { toast.success('Produit créé.'); close() }}
      />
    )
  }
  if (type === 'ticket') {
    return (
      <TicketQuickCreateModal
        open onClose={close}
        onCreated={() => { toast.success('Ticket créé.'); close() }}
      />
    )
  }
  return null
}
