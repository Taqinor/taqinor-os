import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useIsAdmin } from '../../hooks/useHasPermission'
import {
  AlarmClock, CalendarCheck2, ExternalLink, PartyPopper, Plus, Users,
  ClipboardList, BadgeCheck, AtSign, FileText, Flame,
} from 'lucide-react'
import recordsApi from '../../api/recordsApi'
import {
  Button, Badge, Card, CardHeader, CardTitle, CardContent,
  EmptyState, Spinner,
} from '../../ui'

// VX83 — « Ma file » : LA file de travail unique cross-module. Une seule liste
// unifiée (activités + approbations + mentions + relances/leads chauds/devis),
// classée plus-urgent-d'abord, avec un total unique et un en-tête compté, plus
// un quick-add « + À faire » (crée une activité personnelle assignée à soi —
// la promesse XKB4). Remplace la cockpit à 3 buckets : l'union est classée
// serveur, la page rend une seule pile ordonnée.

// Date du jour au format ISO (YYYY-MM-DD).
const todayStr = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Compteur d'activités EN RETARD par responsable (encart admin « Charge de
// l'équipe »), à partir de la liste complète des activités de la société.
function overdueByResponsable(activities, today = todayStr()) {
  const counts = new Map()
  for (const a of activities ?? []) {
    if (a.done) continue
    if (!a.due_date || a.due_date >= today) continue
    const nom = a.assigned_to_nom || 'Non assigné'
    counts.set(nom, (counts.get(nom) || 0) + 1)
  }
  return [...counts.entries()]
    .map(([nom, count]) => ({ nom, count }))
    .sort((a, b) => b.count - a.count)
}

// Icône + ton par famille d'item.
const KIND_META = {
  activite:    { icon: ClipboardList, tone: 'primary' },
  approbation: { icon: BadgeCheck,    tone: 'warning' },
  mention:     { icon: AtSign,        tone: 'primary' },
  relance:     { icon: AlarmClock,    tone: 'danger'  },
  lead_chaud:  { icon: Flame,         tone: 'warning' },
  devis_expire:{ icon: FileText,      tone: 'danger'  },
}

const URGENCY_TONE = { overdue: 'danger', today: 'warning', upcoming: 'success' }
const URGENCY_LABEL = { overdue: 'En retard', today: "Aujourd'hui", upcoming: 'À venir' }

export default function MesActivitesPage() {
  const navigate = useNavigate()
  const isAdmin = useIsAdmin()
  const [file, setFile] = useState({ items: [], total: 0, resume: {} })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [teamActivities, setTeamActivities] = useState([])
  // Quick-add « + À faire » (activité personnelle assignée à soi).
  const [adding, setAdding] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newDue, setNewDue] = useState('')
  const [addBusy, setAddBusy] = useState(false)

  const load = () => {
    setLoading(true)
    setError(false)
    setActionError(null)
    recordsApi.getMaFile()
      .then(r => setFile(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }

  const loadTeam = () => {
    recordsApi.getActivities()
      .then(r => setTeamActivities(r.data.results ?? r.data))
      .catch(() => setTeamActivities([]))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); if (isAdmin) loadTeam() }, [isAdmin])

  // Verbe « Fait » : ne concerne que les activités (les autres familles se
  // traitent sur leur écran d'origine via « Ouvrir »).
  const markDone = async (item) => {
    setActionError(null)
    try {
      await recordsApi.markActivityDone(item.activity_id)
      load(); if (isAdmin) loadTeam()
    } catch { setActionError('Action impossible — réessayez.') }
  }

  const submitNew = async () => {
    const title = newTitle.trim()
    if (!title) return
    setAddBusy(true)
    setActionError(null)
    try {
      // Aucun model/id → le serveur crée une activité PERSONNELLE assignée à
      // soi (XKB4). due_date optionnelle.
      await recordsApi.createActivity({
        summary: title,
        ...(newDue ? { due_date: newDue } : {}),
      })
      setNewTitle(''); setNewDue(''); setAdding(false)
      load()
    } catch { setActionError("La tâche n'a pas pu être créée — réessayez.") }
    finally { setAddBusy(false) }
  }

  const teamOverdue = useMemo(
    () => overdueByResponsable(teamActivities), [teamActivities])

  const resume = file.resume || {}
  const headerParts = []
  if (resume.en_retard) headerParts.push(`${resume.en_retard} en retard`)
  if (resume.aujourdhui) headerParts.push(`${resume.aujourdhui} aujourd'hui`)
  if (resume.approbations) headerParts.push(
    `${resume.approbations} approbation${resume.approbations > 1 ? 's' : ''}`)
  const headerText = headerParts.join(' · ')

  return (
    <div className="page">
      <div className="page-header flex items-center justify-between gap-2">
        <h2>
          <AlarmClock className="mr-2 inline size-5 align-[-3px] text-muted-foreground" aria-hidden="true" />
          Ma file
          {file.total > 0 && <Badge tone="primary" className="ml-2 align-middle">{file.total}</Badge>}
        </h2>
        <Button size="sm" onClick={() => setAdding(v => !v)} data-testid="ma-file-add-toggle">
          <Plus /> À faire
        </Button>
      </div>
      <p className="mb-3 text-sm text-muted-foreground">
        {headerText || 'Tout ce qui vous attend, en une seule file classée par urgence.'}
      </p>

      {adding && (
        <Card className="mb-4 overflow-hidden border-primary/40">
          <CardContent className="flex flex-wrap items-end gap-2 py-3">
            <div className="flex-1 min-w-[12rem]">
              <label className="mb-1 block text-xs text-muted-foreground">Nouvelle tâche</label>
              <input
                type="text"
                className="form-control form-control-sm w-full"
                placeholder="Ex. Rappeler M. Alami"
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') submitNew() }}
                data-testid="ma-file-add-title"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">Échéance</label>
              <input
                type="date" min={todayStr()}
                className="form-control form-control-sm w-auto"
                value={newDue}
                onChange={e => setNewDue(e.target.value)}
              />
            </div>
            <Button size="sm" onClick={submitNew} loading={addBusy} disabled={addBusy || !newTitle.trim()}>
              Ajouter
            </Button>
            <Button size="sm" variant="outline" onClick={() => { setAdding(false); setNewTitle(''); setNewDue('') }}
                    disabled={addBusy}>
              Annuler
            </Button>
          </CardContent>
        </Card>
      )}

      {actionError && (
        <p className="form-error mb-3" role="alert">{actionError}</p>
      )}

      {isAdmin && teamOverdue.length > 0 && (
        <Card className="mb-4 overflow-hidden">
          <CardHeader className="flex-row items-center gap-2">
            <Users className="size-4 text-muted-foreground" aria-hidden="true" />
            <CardTitle className="flex-1">Charge de l'équipe — activités en retard</CardTitle>
            <Badge tone="danger">{teamOverdue.reduce((s, r) => s + r.count, 0)}</Badge>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2 pt-3">
            {teamOverdue.map(r => (
              <span key={r.nom}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-3 py-1 text-sm">
                <span className="font-medium">{r.nom}</span>
                <Badge tone="danger">{r.count}</Badge>
              </span>
            ))}
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </div>
      ) : error ? (
        <EmptyState
          icon={AlarmClock}
          title="Chargement impossible"
          description="La file n'a pas pu être récupérée. Réessayez."
          action={<Button size="sm" onClick={load}>Réessayer</Button>}
          className="mt-1"
        />
      ) : file.total === 0 ? (
        <EmptyState
          icon={PartyPopper}
          title="File vide"
          description="Rien à traiter pour le moment — tout est à jour. 🎉"
          className="mt-1"
        />
      ) : (
        <Card className="overflow-hidden" data-testid="ma-file-list">
          <CardContent className="p-0 sm:p-0">
            <ul className="divide-y divide-border">
              {file.items.map((item, idx) => {
                const meta = KIND_META[item.kind] || { icon: ClipboardList, tone: 'primary' }
                const Icon = meta.icon
                const tone = URGENCY_TONE[item.urgency] || 'success'
                return (
                  <li key={`${item.kind}-${item.activity_id ?? item.notification_id ?? item.source_id ?? idx}`}
                      className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <span className="flex-1 min-w-[10rem] text-sm">{item.title}</span>
                    {item.montant && (
                      <span className="text-sm tabular-nums text-muted-foreground">{item.montant} MAD</span>
                    )}
                    {item.due && (
                      <span className="text-xs tabular-nums text-muted-foreground">{String(item.due).slice(0, 10)}</span>
                    )}
                    <Badge tone={tone}>{URGENCY_LABEL[item.urgency] || 'À venir'}</Badge>
                    <span className="inline-flex items-center gap-1.5">
                      {item.kind === 'activite' && item.activity_id && (
                        <Button size="sm" onClick={() => markDone(item)}>
                          <CalendarCheck2 /> Fait
                        </Button>
                      )}
                      {item.link && (
                        <Button size="sm" variant="outline" onClick={() => navigate(item.link)}>
                          <ExternalLink /> Ouvrir
                        </Button>
                      )}
                    </span>
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
