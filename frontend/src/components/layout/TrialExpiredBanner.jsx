// NTDMO20 — bandeau non-bloquant « Votre essai a expiré ».
// Visible UNIQUEMENT quand `company_essai_expire` (servi par /auth/me) est
// vrai — c'est-à-dire quand `CompanyProfile.essai_expire_le` est renseignée
// ET dépassée. Vide par défaut pour TOUTE société existante → rend null,
// aucune régression. Jamais bloquant : aucune action n'est empêchée.
import { useState, useEffect } from 'react'
import { useSelector } from 'react-redux'
import { AlertTriangle } from 'lucide-react'
import { getCurrentTenantTheme, subscribeTenantTheme } from '../../design/tenantTheme'

export default function TrialExpiredBanner() {
  const expired = useSelector((s) => s.auth.user?.company_essai_expire)
  // White-label (SCA29) : le nom de marque vient de TenantTheme/CompanyProfile,
  // JAMAIS d'une chaîne en dur. Sans thème configuré → repli neutre générique.
  const [theme, setTheme] = useState(getCurrentTenantTheme)
  useEffect(() => subscribeTenantTheme(setTheme), [])
  if (!expired) return null
  const nomProduit = theme.nomAffichage || 'cette plateforme'
  return (
    <div
      role="status"
      data-testid="trial-expired-banner"
      className="flex items-center justify-center gap-2 border-b border-red-300/60 bg-red-50 px-4 py-1.5 text-[12.5px] font-medium text-red-800 dark:border-red-500/30 dark:bg-red-950/40 dark:text-red-200"
    >
      <AlertTriangle className="size-3.5" aria-hidden="true" />
      Votre essai a expiré — contactez-nous pour continuer à utiliser {nomProduit}.
    </div>
  )
}
