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
import portailApi from '../../api/portailApi'
import {
  LANGUE_PAR_DEFAUT, LANGUES, chrome, directionLangue, libelle,
} from './langue'
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

   NTPRT34 — langue du portail (FR/AR) : la préférence est SERVEUR (elle suit
   le compte, jamais un cookie), elle ne couvre que la nav et la chrome de ce
   shell, et l'arabe bascule le sens d'écriture (`dir="rtl"`). Une lecture ou
   une écriture en échec laisse la langue courante : le portail ne se met
   jamais à moitié en arabe à cause d'une requête perdue.
   ========================================================================== */

export default function PortalLayout({ titre, titreAr, items, children }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const [marque, setMarque] = useState(getCurrentTenantTheme)
  const [langue, setLangue] = useState(LANGUE_PAR_DEFAUT)

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

  // NTPRT34 — langue choisie par CE compte portail (serveur). Un échec de
  // lecture garde le français : jamais d'erreur visible pour un libellé.
  useEffect(() => {
    let annule = false
    portailApi.preference.get()
      .then((r) => {
        if (!annule && LANGUES.includes(r.data?.langue)) {
          setLangue(r.data.langue)
        }
      })
      .catch(() => {})
    return () => { annule = true }
  }, [])

  const changerLangue = (code) => {
    const precedente = langue
    setLangue(code)
    // La préférence est SERVEUR : si l'écriture échoue, on revient à l'état
    // affiché avant le clic plutôt que de mentir sur ce qui est enregistré.
    portailApi.preference.set(code).catch(() => setLangue(precedente))
  }

  const handleLogout = async () => {
    await dispatch(logoutUser())
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-background text-foreground"
         lang={langue} dir={directionLangue(langue)}>
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-4 py-3">
          {marque.logoUrl
            ? (
              <img src={marque.logoUrl} alt="" aria-hidden="true"
                   className="h-8 w-auto max-w-[160px] object-contain" />
              )
            : null}
          <span className="font-display text-base font-semibold tracking-tight">
            {marque.nomAffichage || libelle({ label: titre, labelAr: titreAr }, langue)}
          </span>
          <span className="ms-auto" />
          <div className="flex items-center gap-1"
               role="group" aria-label={chrome(langue, 'langue')}>
            {LANGUES.map((code) => (
              <Button
                key={code}
                variant={code === langue ? 'secondary' : 'ghost'}
                size="sm"
                aria-pressed={code === langue}
                onClick={() => changerLangue(code)}
              >
                {code.toUpperCase()}
              </Button>
            ))}
          </div>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="size-4" aria-hidden="true" />
            {chrome(langue, 'deconnexion')}
          </Button>
        </div>
        <nav aria-label={chrome(langue, 'navigation')}
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
                  {libelle(item, langue)}
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
