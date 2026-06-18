// N6 — Timeline du chantier : les jalons (signé, matériel commandé, pose
// prévue/réelle, mise en service, réception, clôture) sur un seul écran.
// J43 — portée sur les tokens du système de design (couleurs sémantiques).
import { formatDate } from '../../lib/format'

const MILESTONES = [
  { key: 'date_signature', label: 'Signé', tone: 'var(--muted-foreground)' },
  { key: 'date_materiel_commande', label: 'Matériel commandé', tone: '#a855f7' },
  { key: 'date_pose_prevue', label: 'Pose prévue', tone: 'var(--info)' },
  { key: 'date_pose_reelle', label: 'Pose réelle', tone: 'var(--warning)' },
  { key: 'date_mise_en_service', label: 'Mise en service', tone: '#0ea5e9' },
  { key: 'date_reception', label: 'Réception', tone: 'var(--success)' },
  { key: 'date_cloture', label: 'Clôture', tone: '#15803d' },
]

export default function ChantierTimeline({ installation }) {
  return (
    <div className="flex flex-wrap gap-4">
      {MILESTONES.map((m) => {
        const date = formatDate(installation?.[m.key])
        const done = date !== '—'
        return (
          <div
            key={m.key}
            className="flex min-w-24 flex-col items-center text-center"
            style={{ opacity: done ? 1 : 0.4 }}
          >
            <span
              className="mb-1 size-3.5 rounded-full"
              style={{ background: done ? m.tone : 'var(--border)' }}
            />
            <span className="text-xs font-semibold text-foreground">{m.label}</span>
            <span className="text-[11px] text-muted-foreground">{date}</span>
          </div>
        )
      })}
    </div>
  )
}
