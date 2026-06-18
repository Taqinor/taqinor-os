import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlarmClock, CalendarCheck2, ExternalLink, PartyPopper } from 'lucide-react'
import recordsApi from '../../api/recordsApi'
import {
  Button, Badge, Card, CardHeader, CardTitle, CardContent,
  EmptyState, Spinner,
} from '../../ui'

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
  const [data, setData] = useState({ en_retard: [], aujourdhui: [], a_venir: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = () => {
    setLoading(true)
    setError(false)
    recordsApi.getMyActivities()
      .then(r => setData(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const markDone = async (a) => {
    try { await recordsApi.markActivityDone(a.id); load() } catch { /* */ }
  }

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
                                <Button size="sm" onClick={() => markDone(a)}>
                                  <CalendarCheck2 /> Fait
                                </Button>
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
