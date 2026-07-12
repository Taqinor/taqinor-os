// N6 — Timeline du chantier : les jalons (signé, matériel commandé, pose
// prévue/réelle, mise en service, réception, clôture) sur un seul écran.
// J43 — portée sur les tokens du système de design (couleurs sémantiques).
import { formatDate } from '../../lib/format'

const MILESTONES = [
  { key: 'date_signature', label: 'Signé', tone: 'var(--muted-foreground)' },
  { key: 'date_materiel_commande', label: 'Matériel commandé', tone: 'var(--milestone-materiel)' },
  { key: 'date_pose_prevue', label: 'Pose prévue', tone: 'var(--info)' },
  { key: 'date_pose_reelle', label: 'Pose réelle', tone: 'var(--warning)' },
  { key: 'date_mise_en_service', label: 'Mise en service', tone: 'var(--milestone-service)' },
  { key: 'date_reception', label: 'Réception', tone: 'var(--success)' },
  { key: 'date_cloture', label: 'Clôture', tone: 'var(--milestone-cloture)' },
]

// N6 — jalons du dossier réglementaire (loi 82-21) : affichés à côté des jalons
// de pose UNIQUEMENT quand la date correspondante est renseignée.
const DOSSIER_MILESTONES = [
  { key: 'dossier_date_depot', label: 'Dossier déposé', tone: 'var(--milestone-dossier-depot)' },
  { key: 'dossier_date_approbation', label: 'Dossier approuvé', tone: 'var(--milestone-dossier-approbation)' },
]

function Milestone({ label, tone, date, done }) {
  return (
    <div
      className="flex min-w-24 flex-col items-center text-center"
      style={{ opacity: done ? 1 : 0.4 }}
    >
      <span
        className="mb-1 size-3.5 rounded-full"
        style={{ background: done ? tone : 'var(--border)' }}
      />
      <span className="text-xs font-semibold text-foreground">{label}</span>
      <span className="text-[11px] text-muted-foreground">{date}</span>
    </div>
  )
}

export default function ChantierTimeline({ installation }) {
  // On insère les jalons dossier renseignés à la suite, sans casser l'ordre des
  // jalons de pose existants.
  const dossier = DOSSIER_MILESTONES.filter(
    (m) => formatDate(installation?.[m.key]) !== '—')
  return (
    <div className="flex flex-wrap gap-4">
      {MILESTONES.map((m) => {
        const date = formatDate(installation?.[m.key])
        return (
          <Milestone key={m.key} label={m.label} tone={m.tone}
                     date={date} done={date !== '—'} />
        )
      })}
      {dossier.map((m) => (
        <Milestone key={m.key} label={m.label} tone={m.tone}
                   date={formatDate(installation?.[m.key])} done />
      ))}
    </div>
  )
}
