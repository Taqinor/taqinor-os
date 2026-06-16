// N6 — Timeline du chantier : les jalons (signé, matériel commandé, pose
// prévue/réelle, mise en service, réception, clôture) sur un seul écran.
const formatDateFR = (iso) => {
  if (!iso) return null
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('fr-FR')
}

const MILESTONES = [
  { key: 'date_signature', label: 'Signé', color: '#64748b' },
  { key: 'date_materiel_commande', label: 'Matériel commandé', color: '#a855f7' },
  { key: 'date_pose_prevue', label: 'Pose prévue', color: '#3b82f6' },
  { key: 'date_pose_reelle', label: 'Pose réelle', color: '#f59e0b' },
  { key: 'date_mise_en_service', label: 'Mise en service', color: '#0ea5e9' },
  { key: 'date_reception', label: 'Réception', color: '#16a34a' },
  { key: 'date_cloture', label: 'Clôture', color: '#15803d' },
]

export default function ChantierTimeline({ installation }) {
  return (
    <div className="form-section">
      <div className="form-section-header">
        <span className="form-section-title">📈 Timeline</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
        {MILESTONES.map((m) => {
          const date = formatDateFR(installation?.[m.key])
          return (
            <div key={m.key} style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              minWidth: 96, opacity: date ? 1 : 0.4,
            }}>
              <span style={{
                width: 14, height: 14, borderRadius: '50%',
                background: date ? m.color : '#cbd5e1', marginBottom: 4,
              }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: '#334155', textAlign: 'center' }}>
                {m.label}
              </span>
              <span style={{ fontSize: 11, color: '#64748b' }}>{date ?? '—'}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
