// NTCRM9 — Org chart visuel du compte (onglet « Organigramme » sur la fiche
// client). Liste les ContactClient (NTCRM8) groupés par rôle d'achat avec
// badges couleur + une carte hiérarchique CSS simple (pas de canvas), et des
// actions rapides (appeler/WhatsApp/email) par contact.
import { useEffect, useState } from 'react'
import api from '../../../api/axios'
import { Spinner, EmptyState, Card, Badge } from '../../../ui'
import { toast } from '../../../ui/confirm'

const ROLE_LABELS = {
  decideur: 'Décideur',
  influenceur: 'Influenceur',
  utilisateur: 'Utilisateur',
  gatekeeper: 'Gatekeeper',
  sponsor: 'Sponsor',
  autre: 'Autre',
}

const ROLE_ORDER = ['decideur', 'sponsor', 'influenceur', 'gatekeeper', 'utilisateur', 'autre']

const ROLE_COLORS = {
  decideur: 'bg-purple-100 text-purple-800',
  sponsor: 'bg-blue-100 text-blue-800',
  influenceur: 'bg-amber-100 text-amber-800',
  gatekeeper: 'bg-red-100 text-red-800',
  utilisateur: 'bg-green-100 text-green-800',
  autre: 'bg-gray-100 text-gray-800',
}

export default function OrgChartTab({ clientId }) {
  const [contacts, setContacts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!clientId) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- état de chargement avant le fetch
    setLoading(true)
    api.get('/contacts/contacts-client/', { params: { client: clientId } })
      .then((res) => setContacts(res.data?.results ?? res.data ?? []))
      .catch(() => toast.error("Impossible de charger l'organigramme."))
      .finally(() => setLoading(false))
  }, [clientId])

  if (loading) return <Spinner />
  if (contacts.length === 0) {
    return <EmptyState title="Aucun contact" description="Ajoutez des contacts pour construire l'organigramme d'achat." />
  }

  const groupes = ROLE_ORDER
    .map((role) => ({ role, items: contacts.filter((c) => c.role_achat === role) }))
    .filter((g) => g.items.length > 0)

  return (
    <div className="space-y-4" data-testid="org-chart-tab">
      {groupes.map((g) => (
        <Card key={g.role} className="p-4 space-y-2">
          <Badge className={ROLE_COLORS[g.role]}>{ROLE_LABELS[g.role]}</Badge>
          <ul className="space-y-2 mt-2">
            {g.items.map((contact) => (
              <li key={contact.id} className="flex items-center justify-between text-sm border-b pb-2">
                <div>
                  <div className="font-medium">
                    {contact.nom} {contact.prenom}
                    {contact.contact_principal && (
                      <span className="ml-2 text-xs text-muted-foreground">(principal)</span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">{contact.poste}</div>
                </div>
                <div className="flex gap-2">
                  {contact.telephone && (
                    <a href={`tel:${contact.telephone}`} className="text-xs underline">Appeler</a>
                  )}
                  {contact.whatsapp && (
                    <a
                      href={`https://wa.me/${contact.whatsapp.replace(/\D/g, '')}`}
                      target="_blank" rel="noreferrer" className="text-xs underline"
                    >
                      WhatsApp
                    </a>
                  )}
                  {contact.email && (
                    <a href={`mailto:${contact.email}`} className="text-xs underline">Email</a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  )
}
