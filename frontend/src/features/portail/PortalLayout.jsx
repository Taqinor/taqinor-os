import { useEffect, useState } from 'react'
import { useDispatch } from 'react-redux'
import { NavLink, useNavigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { logoutUser } from '../auth/store/authSlice'
import {
  getCurrentTenantTheme, resetTenantTheme, setTenantTheme,
  subscribeTenantTheme,
} from '../../design/tenantTheme'
import coreApi from '../../api/coreApi'
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

   NTPRT19 — branding par société : ce shell est le lecteur réseau du portail
   (exactement comme `Layout` l'est pour l'ERP) — il pose `TenantTheme` sur
   <html> via `setTenantTheme`, puis lit la marque publiée. Un échec réseau ou
   un thème absent retombe en SILENCE sur le thème neutre (`tokens.css`) : un
   logo manquant ne casse jamais un écran client.
   ========================================================================== */

export default function PortalLayout({ titre, items, children }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const [marque, setMarque] = useState(getCurrentTenantTheme)

  // Le thème est publié par un pub/sub en mémoire (design/tenantTheme).
  useEffect(() => subscribeTenantTheme(setMarque), [])

  // NTPRT19 — chargement du thème de la société du compte portail connecté.
  // `GET /core/theme/courant/` est ouvert à tout compte authentifié et scopé
  // société côté serveur : un compte portail y lit SA marque, jamais celle
  // d'un autre tenant.
  useEffect(() => {
    let annule = false
    coreApi.theme.getCourant()
      .then((res) => { if (!annule) setTenantTheme(res.data) })
      .catch(() => { if (!annule) resetTenantTheme() })
    return () => { annule = true }
  }, [])

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
