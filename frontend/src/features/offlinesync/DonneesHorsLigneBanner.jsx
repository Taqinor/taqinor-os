// NTMOB27 — bandeau d'ANCIENNETÉ affiché quand un écran est servi depuis le
// cache de LECTURE hors-ligne. Il ne remplace pas la bannière hors-ligne
// globale (M61) : celle-ci dit « vous êtes hors-ligne », celui-ci dit « ce que
// vous lisez date de HH:MM » — la donnée périmée ne se fait jamais passer pour
// fraîche. Rend null si l'écran n'est pas servi du cache.
import { CloudOff } from 'lucide-react'

function heure(ts) {
  try {
    return new Date(ts).toLocaleTimeString('fr-FR',
      { hour: '2-digit', minute: '2-digit' })
  } catch {
    return '—'
  }
}

export default function DonneesHorsLigneBanner({ cachedAt }) {
  if (!cachedAt) return null
  return (
    <div
      role="status"
      data-testid="bandeau-hors-ligne"
      className="flex items-center gap-2 rounded-md border border-border bg-muted px-3 py-2 text-xs text-muted-foreground"
    >
      <CloudOff className="size-4 shrink-0" aria-hidden="true" />
      <span>Données hors-ligne, dernière synchro à {heure(cachedAt)}</span>
    </div>
  )
}
