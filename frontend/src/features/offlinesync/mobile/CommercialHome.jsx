// NTMOB4 — Accueil mobile rôle Commercial : `/mobile/commercial`, rendu
// uniquement en largeur mobile (redirection automatique vers le dashboard
// existant en desktop). Cartes « Mes leads du jour » (relances dues
// aujourd'hui, triées par priorité), « Mes RDV » (agenda du jour via
// reporting/calendar/), « Carte de mes leads » (raccourci vers CartePage
// existante), raccourcis « Nouveau lead » / « Créer devis ». Lecture seule
// via les endpoints crm/reporting EXISTANTS (crm.selectors.relances_du_jour,
// reporting.calendar_events) — aucune nouvelle logique métier.
import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import {
  Target, CalendarClock, Map, UserPlus, FileText, ChevronRight, Phone,
} from 'lucide-react'
import crmApi from '../../../api/crmApi'
import reportingApi from '../../../api/reportingApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent,
  Badge, Button, Spinner, EmptyState,
} from '../../../ui'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import { formatDate } from '../../../lib/format'

// Priorité haute → normale → basse (Lead.Priorite, crm/models.py).
const PRIORITY_ORDER = { haute: 0, normale: 1, basse: 2 }
const PRIORITY_TONE = { haute: 'danger', normale: 'neutral', basse: 'neutral' }

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function sortByPriority(leads) {
  return [...leads].sort((a, b) => {
    const pa = PRIORITY_ORDER[a.priorite] ?? 1
    const pb = PRIORITY_ORDER[b.priorite] ?? 1
    return pa - pb
  })
}

export default function CommercialHome() {
  const isMobile = useIsMobile()
  const navigate = useNavigate()
  const userId = useSelector((s) => s.auth?.user?.id)
  const [leads, setLeads] = useState(null)
  const [events, setEvents] = useState(null)

  useEffect(() => {
    if (!isMobile) return undefined
    let alive = true
    crmApi.getRelances({ scope: 'today' })
      .then((r) => { if (alive) setLeads(sortByPriority(r.data?.results ?? [])) })
      .catch(() => { if (alive) setLeads([]) })
    const day = todayIso()
    reportingApi.getCalendar({ from: day, to: day, assignee: userId || undefined })
      .then((r) => { if (alive) setEvents(r.data?.events ?? []) })
      .catch(() => { if (alive) setEvents([]) })
    return () => { alive = false }
  }, [isMobile, userId])

  if (!isMobile) return <Navigate to="/dashboard" replace />

  return (
    <div className="flex flex-col gap-3 p-3 pb-24">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button
          variant="secondary" className="flex-1 justify-center gap-2"
          onClick={() => navigate('/crm/leads?new=1')}
        >
          <UserPlus className="size-4" aria-hidden="true" /> Nouveau lead
        </Button>
        <Button
          variant="secondary" className="flex-1 justify-center gap-2"
          onClick={() => navigate('/ventes/devis/nouveau')}
        >
          <FileText className="size-4" aria-hidden="true" /> Créer devis
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Target className="size-4 text-muted-foreground" aria-hidden="true" />
                Mes leads du jour
              </CardTitle>
              <CardDescription>Relances dues aujourd'hui, par priorité</CardDescription>
            </div>
            {leads && leads.length > 0 && <Badge tone="warning">{leads.length}</Badge>}
          </div>
        </CardHeader>
        <CardContent>
          {leads === null
            ? <Spinner />
            : leads.length === 0
              ? <EmptyState title="Aucune relance due aujourd'hui" />
              : (
                <ul className="flex flex-col divide-y divide-border">
                  {leads.map((lead) => (
                    <li key={lead.id}>
                      <button
                        type="button"
                        className="flex w-full items-center justify-between gap-2 py-2 text-left"
                        onClick={() => navigate(`/crm/leads/${lead.id}`)}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">
                            {[lead.prenom, lead.nom].filter(Boolean).join(' ') || `Lead #${lead.id}`}
                          </span>
                          {lead.telephone && (
                            <span className="flex items-center gap-1 text-xs text-muted-foreground">
                              <Phone className="size-3" aria-hidden="true" /> {lead.telephone}
                            </span>
                          )}
                        </span>
                        {lead.priorite && (
                          <Badge tone={PRIORITY_TONE[lead.priorite] || 'neutral'}>
                            {lead.priorite}
                          </Badge>
                        )}
                        <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock className="size-4 text-muted-foreground" aria-hidden="true" />
            Mes RDV
          </CardTitle>
          <CardDescription>Agenda du jour</CardDescription>
        </CardHeader>
        <CardContent>
          {events === null
            ? <Spinner />
            : events.length === 0
              ? <EmptyState title="Aucun rendez-vous aujourd'hui" />
              : (
                <ul className="flex flex-col divide-y divide-border">
                  {events.map((ev) => (
                    <li key={ev.id} className="flex items-center justify-between gap-2 py-2">
                      <span className="min-w-0 flex-1 truncate">{ev.title}</span>
                      <span className="text-xs text-muted-foreground">{formatDate(ev.date)}</span>
                    </li>
                  ))}
                </ul>
              )}
        </CardContent>
      </Card>

      <Button
        variant="outline" className="justify-center gap-2"
        onClick={() => navigate('/carte')}
      >
        <Map className="size-4" aria-hidden="true" /> Carte de mes leads
      </Button>
    </div>
  )
}
