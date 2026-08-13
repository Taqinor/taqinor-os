// NTMOB26 — Accueil mobile rôle « Commercial responsable » :
// `/mobile/equipe-commerciale`. Reprend l'accueil individuel NTMOB4 (onglet
// « Moi ») et l'étend d'un onglet « Équipe » : classement des relances EN
// RETARD par commercial. Aucune agrégation nouvelle — `crm/leads/relances/`
// applique déjà la PORTÉE DE VISIBILITÉ (`scope_queryset`, Feature F), donc un
// responsable y reçoit les leads de son sous-arbre ; on ne fait que grouper par
// `owner` côté client. Distinct de l'écran desktop « Mes équipes » (FE-ZSAL3) :
// ici uniquement la version mobile condensée.
import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Users, ChevronRight } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent,
  Badge, Spinner, EmptyState, Segmented,
} from '../../../ui'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import CommercialHome from './CommercialHome'
import { classementParCommercial } from './equipeCommerciale'

const ONGLETS = [
  { value: 'moi', label: 'Moi' },
  { value: 'equipe', label: 'Équipe' },
]

export default function EquipeCommercialeHome() {
  const isMobile = useIsMobile()
  const navigate = useNavigate()
  const [onglet, setOnglet] = useState('moi')
  const [enRetard, setEnRetard] = useState(null)

  useEffect(() => {
    if (!isMobile) return undefined
    let alive = true
    crmApi.getRelances({ scope: 'overdue' })
      .then((r) => { if (alive) setEnRetard(r.data?.results ?? []) })
      .catch(() => { if (alive) setEnRetard([]) })
    return () => { alive = false }
  }, [isMobile])

  if (!isMobile) return <Navigate to="/dashboard" replace />

  const classement = classementParCommercial(enRetard ?? [])

  return (
    <div className="flex flex-col gap-3 p-3 pb-24">
      <Segmented value={onglet} onChange={setOnglet} options={ONGLETS} />

      {onglet === 'moi' ? (
        <CommercialHome />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="size-4 text-muted-foreground" aria-hidden="true" />
              Relances en retard par commercial
            </CardTitle>
            <CardDescription>Mon équipe, du plus chargé au moins</CardDescription>
          </CardHeader>
          <CardContent>
            {enRetard === null
              ? <Spinner />
              : classement.length === 0
                ? <EmptyState title="Aucune relance en retard dans l'équipe" />
                : (
                  <ul className="flex flex-col gap-3">
                    {classement.map((c) => (
                      <li key={c.id}>
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{c.nom}</span>
                          <Badge tone="danger">{c.leads.length}</Badge>
                        </div>
                        <ul className="flex flex-col divide-y divide-border">
                          {c.leads.map((lead) => (
                            <li key={lead.id}>
                              <button
                                type="button"
                                className="flex w-full items-center justify-between gap-2 py-1.5 text-left text-sm"
                                onClick={() => navigate(`/crm/leads/${lead.id}`)}
                              >
                                <span className="min-w-0 flex-1 truncate">
                                  {[lead.prenom, lead.nom].filter(Boolean).join(' ')
                                    || `Lead #${lead.id}`}
                                </span>
                                <ChevronRight
                                  className="size-4 text-muted-foreground"
                                  aria-hidden="true" />
                              </button>
                            </li>
                          ))}
                        </ul>
                      </li>
                    ))}
                  </ul>
                )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
