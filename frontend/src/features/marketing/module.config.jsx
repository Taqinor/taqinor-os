/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { CalendarDays, Megaphone } from 'lucide-react'

/* ============================================================================
   MARKETING (XMKT30) — configuration du module « Marketing » (auto-enregistré).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/marketing/` ; le registre `router/moduleRoutes.jsx`
   la collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar ni
   à routes.meta. Gatée « responsable / admin », comme les autres écrans de
   pilotage commercial/comptable (compta, flotte). Écran chargé en lazy
   (code-splitting préservé).
   ========================================================================== */

const MarketingCalendarScreen = lazy(() => import('./MarketingCalendarScreen'))
// XMKT34/XMKT10 — éditeur de campagnes (bouton IA key-gated, canal WhatsApp).
const CampagnesScreen = lazy(() => import('./CampagnesScreen'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'marketing',
  order: 55,
  nav: {
    label: 'MARKETING',
    accent: 'brass', // VX8 — commercial/croissance = accent brass (dérivé)
    items: [
      { to: '/marketing/calendrier', label: 'Calendrier marketing', icon: <CalendarDays size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/marketing/campagnes', label: 'Campagnes', icon: <Megaphone size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta — du plus spécifique au plus général.
  titles: [
    ['/marketing/calendrier', 'Calendrier marketing'],
    ['/marketing/campagnes', 'Campagnes marketing'],
  ],
  sectionLabels: { marketing: 'Marketing' },
  routes: [
    { path: '/marketing/calendrier', component: MarketingCalendarScreen, roles: ROLES },
    { path: '/marketing/campagnes', component: CampagnesScreen, roles: ROLES },
  ],
}

export default config
