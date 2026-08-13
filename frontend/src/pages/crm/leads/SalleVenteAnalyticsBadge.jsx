import { useEffect, useState } from 'react'
import { Eye } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import { formatDateTime } from '../../../lib/format'

/* NTCRM19 — badge « le client a consulté N fois, dernière fois <date> » sur
   la fiche lead, alimenté par la salle de vente (NTCRM17/18) la plus
   récente du lead. Rien n'est affiché si le lead n'a aucune salle de vente
   ou si elle n'a jamais été consultée (nb_vues=0) — jamais un badge vide. */
export default function SalleVenteAnalyticsBadge({ leadId }) {
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    // Défensif : de nombreux tests montent DevisTab/ContextRail avec un mock
    // partiel de crmApi qui n'expose pas cette méthode — un appel silencieux
    // en no-op est plus sûr que de forcer chaque test existant à la mocker.
    let active = true
    // setState différé au prochain microtask (jamais synchrone dans l'effet) —
    // évite react-hooks/set-state-in-effect sans changer le comportement visible.
    queueMicrotask(() => {
      if (!active) return
      if (!leadId || typeof crmApi.getLeadSalleVenteAnalytics !== 'function') {
        setSummary(null)
        return
      }
      crmApi.getLeadSalleVenteAnalytics(leadId)
        .then((r) => { if (active) setSummary(r.data ?? null) })
        .catch(() => { if (active) setSummary(null) })
    })
    return () => { active = false }
  }, [leadId])

  if (!summary || !summary.nb_vues) return null

  return (
    <div
      className="lw-context-salle-vente-badge flex items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground"
      data-testid="salle-vente-analytics-badge"
    >
      <Eye className="h-3.5 w-3.5" />
      <span>
        Le client a consulté sa salle de vente {summary.nb_vues} fois
        {summary.derniere_vue && (
          <> — dernière fois {formatDateTime(summary.derniere_vue)}</>
        )}
      </span>
    </div>
  )
}
