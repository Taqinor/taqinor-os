// Liste « Historique » d'un devis / d'une facture (ENF19) : même rendu des
// entrées de chatter (note manuelle ou changement de champ ancien → nouveau).
import { formatDateTime } from '../../lib/format.js'

export default function HistoriqueActivitesListe({ activites }) {
  return (
    <ul className="space-y-1 text-sm">
      {activites.map(a => (
        <li key={a.id} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="text-xs text-muted-foreground">
            {a.created_at ? formatDateTime(a.created_at) : '—'}
            {a.user_nom ? ` · ${a.user_nom}` : ''}
          </span>
          <span>
            {a.body
              ? a.body
              : (
                <>
                  <strong>{a.field_label || a.field}</strong>
                  {' : '}
                  <span className="text-muted-foreground">{a.old_value || '—'}</span>
                  {' → '}
                  <span>{a.new_value || '—'}</span>
                </>
              )}
          </span>
        </li>
      ))}
    </ul>
  )
}
