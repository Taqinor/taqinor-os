import { useEffect, useState } from 'react'
import { useDispatch } from 'react-redux'
import { NavLink, useNavigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { logoutUser } from '../auth/store/authSlice'
import { getCurrentTenantTheme, subscribeTenantTheme } from '../../design/tenantTheme'
import { Button } from '../../ui'

/* ============================================================================
   NTPRT8/20/27 — Shell des PORTAILS EXTERNES (client / fournisseur /
   partenaire).
   ----------------------------------------------------------------------------
   Volontairement DISTINCT du shell ERP interne (`components/layout/Layout`) :
   pas de sidebar métier, pas de palette de commandes, pas de copilote, pas de
   coachmarks — un client externe ne doit voir AUCUNE surface interne. On
   réutilise en revanche les tokens `design/` et les primitives `ui/` (même
   design system, aucune duplication de style).

   Le branding par société (`TenantTheme`) est posé par NTPRT19 ; ce shell lit
   simplement les variables CSS de marque déjà appliquées et retombe sur le nom
   par défaut si aucune n'est posée.
   ========================================================================== */

export default function PortalLayout({ titre, items, children }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const [marque, setMarque] = useState(getCurrentTenantTheme)

  // NTPRT19 — le thème est publié par un pub/sub en mémoire (design/
  // tenantTheme) : on s'y abonne, le shell n'est jamais lecteur réseau.
  useEffect(() => subscribeTenantTheme(setMarque), [])

  const handleLogout = async () => {
    await dispatch(logoutUser())
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-3">
          {marque.logoUrl
            ? (
              <img src={marque.logoUrl} alt="" aria-hidden="true"
                   className="h-8 w-auto max-w-[160px] object-contain" />
              )
            : null}
          <span className="font-display text-base font-semibold tracking-tight">
            {marque.nomAffichage || titre}
          </span>
          <span className="ml-auto" />
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="size-4" aria-hidden="true" />
            Se déconnecter
          </Button>
        </div>
        <nav aria-label="Navigation du portail"
             className="mx-auto max-w-5xl overflow-x-auto px-4">
          <ul className="flex min-w-max items-center gap-1 pb-2">
            {(items || []).map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => [
                    'inline-flex items-center rounded-md px-3 py-1.5 text-sm',
                    isActive
                      ? 'bg-muted font-medium text-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                  ].join(' ')}
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <main id="contenu" tabIndex={-1}
            className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-6">
        {children}
      </main>
    </div>
  )
}
