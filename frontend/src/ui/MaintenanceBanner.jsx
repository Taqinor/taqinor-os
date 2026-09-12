import { useEffect, useState } from 'react'
import { AlertTriangle, Clock } from 'lucide-react'
import coreApi from '../api/coreApi'

/* ============================================================================
   NTOBS9 — bannière in-app persistante des fenêtres de maintenance à venir
   (≤72h) ou en cours. Rend null tant qu'aucune fenêtre n'est pertinente pour
   la société de l'utilisateur (comportement historique inchangé). Poll léger
   (2 min) : une fenêtre annulée retire la bannière au prochain rafraîchissement.
   ========================================================================== */

const POLL_INTERVAL_MS = 2 * 60 * 1000

function formatCountdown(debuteLeIso) {
  const ms = new Date(debuteLeIso).getTime() - Date.now()
  if (ms <= 0) return null
  const heures = Math.floor(ms / (1000 * 60 * 60))
  const minutes = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60))
  if (heures >= 1) return `dans ${heures} h`
  return `dans ${Math.max(1, minutes)} min`
}

export default function MaintenanceBanner() {
  const [fenetres, setFenetres] = useState([])

  useEffect(() => {
    let active = true
    const charger = () => {
      coreApi.maintenanceWindows.actives()
        .then((r) => { if (active) setFenetres(r.data ?? []) })
        .catch(() => { if (active) setFenetres([]) })
    }
    charger()
    const interval = setInterval(charger, POLL_INTERVAL_MS)
    return () => { active = false; clearInterval(interval) }
  }, [])

  if (fenetres.length === 0) return null

  // Une bannière EN COURS prime toujours sur une simple annonce à venir.
  const fenetre = fenetres.find((f) => f.statut === 'en_cours') || fenetres[0]
  const enCours = fenetre.statut === 'en_cours'
  const countdown = enCours ? null : formatCountdown(fenetre.debute_le)

  return (
    <div
      role="status"
      data-testid="maintenance-banner"
      className={
        enCours
          ? 'flex items-center justify-center gap-2 border-b border-red-300/60 bg-red-50 px-4 py-1.5 text-[12.5px] font-medium text-red-800 dark:border-red-500/30 dark:bg-red-950/40 dark:text-red-200'
          : 'flex items-center justify-center gap-2 border-b border-amber-300/60 bg-amber-50 px-4 py-1.5 text-[12.5px] font-medium text-amber-800 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-200'
      }
    >
      {enCours ? (
        <AlertTriangle className="size-3.5" aria-hidden="true" />
      ) : (
        <Clock className="size-3.5" aria-hidden="true" />
      )}
      {enCours ? (
        <span>Maintenance en cours — dégradation possible.{' '}
          {fenetre.description}</span>
      ) : (
        <span>
          Fenêtre de maintenance planifiée{countdown ? ` ${countdown}` : ''}
          {fenetre.impact && fenetre.impact !== 'aucun' ? ` (${fenetre.impact})` : ''}.
        </span>
      )}
    </div>
  )
}
