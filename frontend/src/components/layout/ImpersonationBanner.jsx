// NTADM22 — bandeau PERMANENT « Session support active — {nom} vous assiste ».
//
// Visible UNIQUEMENT pendant une session d'impersonation consentie : le serveur
// répond `{active: false}` pour toute requête ordinaire, le bandeau rend alors
// null → aucun utilisateur non concerné n'est affecté.
//
// L'utilisateur assisté doit SAVOIR, en permanence et sans ambiguïté, qu'un
// tiers agit dans son espace : c'est la contrepartie visible du consentement
// qu'il a donné. Le bandeau n'est donc jamais masquable.
import { useEffect, useState } from 'react'
import { LifeBuoy } from 'lucide-react'
import adminopsApi from '../../api/adminopsApi'

export default function ImpersonationBanner() {
  const [session, setSession] = useState(null)

  useEffect(() => {
    let annule = false
    adminopsApi.sessionImpersonationActive()
      .then(({ data }) => {
        if (!annule && data?.active) setSession(data)
      })
      .catch(() => { /* best-effort : jamais bloquant pour la page */ })
    return () => { annule = true }
  }, [])

  if (!session) return null

  return (
    <div
      role="status"
      data-testid="impersonation-banner"
      className="flex items-center justify-center gap-2 border-b border-rose-300/60 bg-rose-50 px-4 py-1.5 text-[12.5px] font-medium text-rose-800 dark:border-rose-500/30 dark:bg-rose-950/40 dark:text-rose-200"
    >
      <LifeBuoy className="size-3.5" aria-hidden="true" />
      {session.message
        || `Session support active — ${session.support_nom} vous assiste`}
    </div>
  )
}
