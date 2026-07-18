import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from '../../../features/crm/workspace/LeadWorkspace'
import { Spinner, EmptyState, Button } from '../../../ui'

/* VX22 — Une vraie page lead : route `/crm/leads/:id`.
   ----------------------------------------------------------------------------
   Jusqu'ici la fiche lead ne vivait QUE comme overlay de `LeadsPage`
   (`?lead=<id>` dépendant du cache de la liste déjà chargée) : pas de
   deep-link fiable, F5 pouvait retomber sur une liste vide selon le filtre,
   et un ctrl-clic depuis Kanban/Liste ouvrait un nouvel onglet... sur la
   liste, pas la fiche.

   Cette page est ADRESSABLE : elle charge le lead via `crmApi.getLead(id)`
   (jamais depuis le cache Redux de la liste, qui peut être vide/filtré/absent
   au premier chargement), rend le même `LeadForm` qu'ailleurs, et `onClose`
   ramène vers `/crm/leads` (la liste). Le flux overlay rapide du Kanban reste
   inchangé (LeadsPage garde `?lead=`) — cette page est l'ADRESSE canonique,
   pas un remplacement du panneau rapide. */
export default function LeadDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [lead, setLead] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect -- init loading au changement d'id
    setLoading(true)
    setNotFound(false)
    setLead(null)
    crmApi.getLead(id)
      .then((r) => { if (!cancelled) setLead(r.data) })
      .catch(() => { if (!cancelled) setNotFound(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [id])

  const backToList = () => navigate('/crm/leads')

  if (loading) {
    return (
      <p className="page-loading"><Spinner /> Chargement du lead…</p>
    )
  }

  if (notFound || !lead) {
    return (
      <EmptyState
        title="Lead introuvable"
        description="Ce lead n'existe pas ou a été supprimé."
        action={<Button size="sm" onClick={backToList}>Retour à la liste</Button>}
      />
    )
  }

  return (
    // LW13 — la route détail rend le LeadWorkspace en PLEINE PAGE (parité de
    // fonctionnalités avec le flux liste : même cockpit, mêmes rails).
    <LeadWorkspace
      variant="page"
      lead={lead}
      onClose={backToList}
      onSaved={() => {
        // Recharge la fiche depuis le serveur pour refléter la modification
        // (ex. devis créé inline) — même logique que LeadsPage.onSaved, mais
        // ciblée sur CE lead plutôt qu'un refetch de liste.
        crmApi.getLead(id).then((r) => setLead(r.data)).catch(() => {})
      }}
    />
  )
}
