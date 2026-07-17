import { useEffect, useState } from 'react'
import { BellRing } from 'lucide-react'
import assurancesApi from './assurancesApi'

/* ============================================================================
   NTASS28 — Bandeau « X polices / attestations expirent sous 30 jours ».
   ----------------------------------------------------------------------------
   Lit le tableau de bord assurances (NTASS21) et affiche un rappel visuel sur
   l'écran des polices. Complète l'intégration des alertes NTASS8/NTASS18 dans
   le centre de notifications (`notify()` côté commande) : ici, le rappel
   permanent à l'écran. Lecture seule, silencieux si rien n'expire.
   ========================================================================== */

export default function ExpirationBanner() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    assurancesApi.getTableauBord()
      .then((res) => setStats(res.data))
      .catch(() => setStats(null))
  }, [])

  const polices = stats?.polices_expirant_30j ?? 0
  const attestations = stats?.attestations_expirant_30j ?? 0
  if (!polices && !attestations) return null

  const parts = []
  if (polices) parts.push(`${polices} police(s)`)
  if (attestations) parts.push(`${attestations} attestation(s)`)

  return (
    <div
      role="status"
      className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200"
    >
      <BellRing className="size-4 shrink-0" aria-hidden="true" />
      <span>
        {parts.join(' et ')} expire(nt) sous 30 jours — pensez au renouvellement.
      </span>
    </div>
  )
}
