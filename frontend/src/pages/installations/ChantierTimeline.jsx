// Timeline d'un chantier (N5) — lecture seule. Affiche, sur un écran, les
// dates clés dans l'ordre du cycle : signé/créé, pose prévue, pose réelle,
// mise en service, clôture (quand statut = CLOTURE).
const formatDateFr = (iso) => {
  if (!iso) return null
  // Accepte une date AAAA-MM-JJ comme un datetime ISO.
  const d = iso.length <= 10 ? new Date(`${iso}T00:00:00`) : new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('fr-FR')
}

export default function ChantierTimeline({ installation }) {
  const it = installation ?? {}
  const isCloture = it.statut === 'cloture'

  const steps = [
    { label: 'Chantier créé', date: it.date_creation },
    { label: 'Pose prévue', date: it.date_pose_prevue },
    { label: 'Pose réalisée', date: it.date_pose_reelle },
    { label: 'Mise en service', date: it.date_mise_en_service },
    {
      label: 'Clôture',
      // La clôture n'a pas de champ date dédié : on la marque faite quand le
      // statut est CLOTURE (date la plus récente connue, sinon « — »).
      date: isCloture
        ? (it.date_mise_en_service ?? it.date_modification ?? null)
        : null,
      pendingUnlessCloture: true,
    },
  ]

  return (
    <div className="cd-timeline">
      {steps.map((step, i) => {
        const formatted = formatDateFr(step.date)
        const done = Boolean(formatted)
        const cls = [
          'cd-tl-item',
          done ? 'cd-tl-done' : 'cd-tl-pending',
        ].join(' ')
        return (
          <div key={i} className={cls}>
            <span className="cd-tl-dot" />
            <div className="cd-tl-label">{step.label}</div>
            <div className="cd-tl-date">
              {formatted ?? (step.pendingUnlessCloture ? 'Non clôturé' : '—')}
            </div>
          </div>
        )
      })}
    </div>
  )
}
