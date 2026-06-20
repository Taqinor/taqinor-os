import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { AlarmClock, CalendarCheck2, CalendarClock, ExternalLink, PartyPopper, Users } from 'lucide-react'
import recordsApi from '../../api/recordsApi'
import {
  Button, Badge, Card, CardHeader, CardTitle, CardContent,
  EmptyState, Spinner,
} from '../../ui'

// Date du jour au format ISO (YYYY-MM-DD), pour comparer aux échéances.
const todayStr = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Compteur d'activités EN RETARD par responsable, à partir de la liste complète
// des activités de la société (ouvertes, échéance dépassée). Logique pure →
// alimente le panneau admin « Charge de l'équipe ».
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

// Buckets de la cockpit : clé API, libellé FR, ton (Badge / point de couleur).
const BUCKETS = [
  ['en_retard', 'En retard', 'danger'],
  ['aujourdhui', "Aujourd'hui", 'warning'],
  ['a_venir', 'À venir', 'success'],
]

const DOT = {
  danger: 'bg-destructive',
  warning: 'bg-warning',
  success: 'bg-success',
}

// Lien profond vers l'enregistrement parent de l'activité.
const targetLink = (a) => {
  if (a.target_model === 'crm.lead') return `/crm/leads?lead=${a.object_id}`
  if (a.target_model === 'crm.client') return '/crm'
  if (a.target_model === 'installations.installation') return '/chantiers'
  if (a.target_model === 'sav.ticket') return '/sav'
  return null
}

export default function MesActivitesPage() {
  const navigate = useNavigate()
  const isAdmin = useSelector((s) => s.auth.role === 'admin')
  const [data, setData] = useState({ en_retard: [], aujourdhui: [], a_venir: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // Erreur d'ACTION (marquer fait / reporter) : distincte de l'échec de
  // chargement (qui, lui, remplace la liste par un état d'erreur).
  const [actionError, setActionError] = useState(null)
  // Reprogrammation inline d'une activité (« Reporter »).
  const [reschedId, setReschedId] = useState(null)
  const [reschedDate, setReschedDate] = useState('')
  // « Charge de l'équipe » (admin) : activités en retard par responsable, depuis
  // la liste complète des activités de la société (l'endpoint « mine » ne
  // renvoie que celles de l'utilisateur courant).
  const [teamActivities, setTeamActivities] = useState([])

  const load = () => {
    setLoading(true)
    setError(false)
    setActionError(null)
    recordsApi.getMyActivities()
      .then(r => setData(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }

  const loadTeam = () => {
    // Liste complète (toutes les activités ouvertes de la société) ; échec
    // silencieux : la charge d'équipe est un encart secondaire, pas la page.
    recordsApi.getActivities()
      .then(r => setTeamActivities(r.data.results ?? r.data))
      .catch(() => setTeamActivities([]))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); if (isAdmin) loadTeam() }, [isAdmin])

  const markDone = async (a) => {
    setActionError(null)
    try {
      await recordsApi.markActivityDone(a.id)
      load(); if (isAdmin) loadTeam()
    } catch { setActionError('Action impossible — réessayez.') }
  }

  const openResched = (a) => {
    setReschedId(a.id)
    setReschedDate(a.due_date || todayStr())
    setActionError(null)
  }
  const cancelResched = () => { setReschedId(null); setReschedDate('') }
  const saveResched = async (a) => {
    if (!reschedDate) return
    if (reschedDate < todayStr()) {
      setActionError("L'échéance ne peut pas être dans le passé.")
      return
    }
    setActionError(null)
    try {
      await recordsApi.updateActivity(a.id, { due_date: reschedDate })
      cancelResched()
      load(); if (isAdmin) loadTeam()
    } catch { setActionError('Action impossible — réessayez.') }
  }

  const teamOverdue = useMemo(
    () => overdueByResponsable(teamActivities), [teamActivities])

  const total = data.en_retard.length + data.aujourdhui.length + data.a_venir.length

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          <AlarmClock className="mr-2 inline size-5 align-[-3px] text-muted-foreground" aria-hidden="true" />
          Mes activités
          {total > 0 && <Badge tone="primary" className="ml-2 align-middle">{total}</Badge>}
        </h2>
      </div>
      <p className="mb-3 text-sm text-muted-foreground">
        Vos activités planifiées, regroupées par échéance.
      </p>

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
          description="Les activités n'ont pas pu être récupérées. Réessayez."
          action={<Button size="sm" onClick={load}>Réessayer</Button>}
          className="mt-1"
        />
      ) : total === 0 ? (
        <EmptyState
          icon={PartyPopper}
          title="Aucune activité planifiée"
          description="Rien à traiter pour le moment — tout est à jour. 🎉"
          className="mt-1"
        />
      ) : (
        <div className="flex flex-col gap-5">
          {BUCKETS.map(([key, label, tone]) => (
            data[key].length > 0 && (
              <Card key={key} className="overflow-hidden">
                <CardHeader className="flex-row items-center gap-2">
                  <span aria-hidden="true" className={`size-2 rounded-full ${DOT[tone]}`} />
                  <CardTitle className="flex-1">{label}</CardTitle>
                  <Badge tone={tone}>{data[key].length}</Badge>
                </CardHeader>
                <CardContent className="p-0 sm:p-0">
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Type</th><th>Résumé</th><th>Échéance</th>
                          <th>Enregistrement</th><th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {data[key].map(a => {
                          const link = targetLink(a)
                          return (
                            <tr key={a.id}>
                              <td>{a.activity_type_icone} {a.activity_type_nom}</td>
                              <td>{a.summary || '—'}</td>
                              <td className="tabular-nums">{a.due_date || '—'}</td>
                              <td>
                                {link ? (
                                  <Button size="sm" variant="outline" onClick={() => navigate(link)}>
                                    <ExternalLink /> {a.target_label || 'Ouvrir'}
                                  </Button>
                                ) : (a.target_label || '—')}
                              </td>
                              <td className="ta-right">
                                {reschedId === a.id ? (
                                  <span className="inline-flex flex-wrap items-center justify-end gap-1.5">
                                    <input type="date" min={todayStr()}
                                           className="form-control form-control-sm w-auto"
                                           value={reschedDate}
                                           onChange={e => setReschedDate(e.target.value)} />
                                    <Button size="sm" onClick={() => saveResched(a)}>OK</Button>
                                    <Button size="sm" variant="outline" onClick={cancelResched}>Annuler</Button>
                                  </span>
                                ) : (
                                  <span className="inline-flex flex-wrap items-center justify-end gap-1.5">
                                    <Button size="sm" variant="outline" onClick={() => openResched(a)}>
                                      <CalendarClock /> Reporter
                                    </Button>
                                    <Button size="sm" onClick={() => markDone(a)}>
                                      <CalendarCheck2 /> Fait
                                    </Button>
                                  </span>
                                )}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )
          ))}
        </div>
      )}
    </div>
  )
}
