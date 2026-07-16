import { useState, useEffect } from 'react'
import { getCurrentTenantTheme, subscribeTenantTheme } from '../../design/tenantTheme'

/* ============================================================================
   ENG31 — Bandeau de marque tenant (white-label) pour les écrans/briefs ENG.
   ----------------------------------------------------------------------------
   S'appuie sur `core.TenantTheme` (FG392) via le pub/sub en mémoire de
   `design/tenantTheme.js` — la MÊME source que le Header du shell (SCA24), sans
   refetch réseau. Quand la société a configuré un thème : logo + nom affichés.
   Repli PROPRE sinon : le nom produit par défaut, aucun logo, aucune exception.
   Rendu dans le brief hebdomadaire (l'artefact « imprimable » du moteur) pour
   qu'il porte la marque du tenant.
   ========================================================================== */

export default function TenantBrand({ fallbackName = '', subtitle = '' }) {
  const [theme, setTheme] = useState(getCurrentTenantTheme)
  useEffect(() => subscribeTenantTheme(setTheme), [])

  // White-label (SCA29) : le nom de marque vient de TenantTheme/CompanyProfile,
  // JAMAIS d'une chaîne en dur. Sans thème configuré → repli propre : aucun nom
  // de marque affiché (comme useDocumentTitle), seul le sous-titre reste.
  const name = theme.nomAffichage || fallbackName
  const logoUrl = theme.logoUrl

  return (
    <div className="ae-tenant-brand" data-testid="ae-tenant-brand"
      style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' }}>
      {logoUrl && (
        <img src={logoUrl} alt={name || 'logo'} data-testid="ae-tenant-logo" className="ae-tenant-logo"
          style={{ maxHeight: 36, maxWidth: 140, objectFit: 'contain' }} />
      )}
      {name && (
        <span data-testid="ae-tenant-name" className="ae-tenant-name"
          style={{ fontWeight: 700 }}>{name}</span>
      )}
      {subtitle && (
        <span className="ae-tenant-subtitle" style={{ color: '#64748b', fontSize: '0.9rem' }}>
          {name ? `— ${subtitle}` : subtitle}
        </span>
      )}
    </div>
  )
}
