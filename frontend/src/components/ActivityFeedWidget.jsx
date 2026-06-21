/**
 * FG8 — ActivityFeedWidget
 * Flux d'activités planifiées unifié (records.Activity) : affiche les
 * activités ouvertes de l'utilisateur courant, bucketées (en retard /
 * aujourd'hui / à venir). Widget léger pour le tableau de bord.
 *
 * Props:
 *   limit (number, défaut 5) — nombre max d'activités par bucket à afficher.
 */
import { useEffect, useState } from 'react'
import { AlertTriangle, CalendarClock, CheckCircle2, Clock } from 'lucide-react'
import recordsApi from '../api/recordsApi'

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit', month: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

const BUCKET_META = {
  en_retard: { label: 'En retard', icon: AlertTriangle, color: '#ef4444' },
  aujourdhui: { label: "Aujourd'hui", icon: Clock, color: '#f59e0b' },
  a_venir: { label: 'À venir', icon: CalendarClock, color: '#3b82f6' },
}

function ActivityRow({ act }) {
  return (
    <div className="activity-feed-row">
      <span className="activity-feed-type">{act.activity_type_icone || '●'}</span>
      <div className="activity-feed-body">
        <span className="activity-feed-summary">
          {act.summary || act.activity_type_nom || 'Activité'}
        </span>
        {act.target_label && (
          <span className="activity-feed-target">{act.target_label}</span>
        )}
      </div>
      {act.due_date && (
        <span className="activity-feed-date">{formatDate(act.due_date)}</span>
      )}
    </div>
  )
}

function BucketSection({ bucketKey, activities, limit }) {
  if (!activities || activities.length === 0) return null
  const meta = BUCKET_META[bucketKey]
  const Icon = meta.icon
  const shown = activities.slice(0, limit)
  return (
    <div className="activity-feed-bucket">
      <div className="activity-feed-bucket-header">
        <Icon size={13} color={meta.color} />
        <span style={{ color: meta.color }}>{meta.label}</span>
        <span className="activity-feed-count">{activities.length}</span>
      </div>
      <div className="activity-feed-rows">
        {shown.map(act => (
          <ActivityRow key={act.id} act={act} />
        ))}
        {activities.length > limit && (
          <div className="activity-feed-more">
            +{activities.length - limit} autres
          </div>
        )}
      </div>
    </div>
  )
}

export default function ActivityFeedWidget({ limit = 5 }) {
  const [buckets, setBuckets] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    recordsApi.getMyActivities()
      .then(res => {
        if (!cancelled) {
          setBuckets(res.data)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Impossible de charger les activités.')
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [])

  const empty = !loading && !error && buckets &&
    !buckets.en_retard?.length && !buckets.aujourdhui?.length && !buckets.a_venir?.length

  return (
    <div className="activity-feed-widget">
      <div className="activity-feed-header">
        <CheckCircle2 size={15} />
        <span>Mes activités</span>
      </div>

      {loading && (
        <div className="activity-feed-placeholder">Chargement…</div>
      )}
      {error && (
        <div className="activity-feed-placeholder activity-feed-error">{error}</div>
      )}
      {empty && (
        <div className="activity-feed-placeholder">Aucune activité ouverte.</div>
      )}
      {!loading && !error && buckets && (
        <>
          <BucketSection bucketKey="en_retard" activities={buckets.en_retard} limit={limit} />
          <BucketSection bucketKey="aujourdhui" activities={buckets.aujourdhui} limit={limit} />
          <BucketSection bucketKey="a_venir" activities={buckets.a_venir} limit={limit} />
        </>
      )}
    </div>
  )
}
