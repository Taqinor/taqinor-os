/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import {
  Truck, Users, Wrench, ShieldCheck, Fuel, LineChart, ClipboardCheck, MapPin,
} from 'lucide-react'

/* ============================================================================
   FLOTTE (UX15–UX20) — configuration du module « Flotte » (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/flotte/` ; le registre `router/moduleRoutes.jsx`
   la collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar ni
   à routes.meta. Toutes les routes/entrées de menu sont gatées
   `['responsable','admin']`. Écrans chargés en lazy (code-splitting préservé).
   ========================================================================== */

const FlotteCockpit = lazy(() => import('./FlotteCockpit'))
const VehiculesList = lazy(() => import('./VehiculesList'))
const ConducteursScreen = lazy(() => import('./ConducteursScreen'))
const EntretienScreen = lazy(() => import('./EntretienScreen'))
const ConformiteScreen = lazy(() => import('./ConformiteScreen'))
const CarburantScreen = lazy(() => import('./CarburantScreen'))
const AnalyseCoutsScreen = lazy(() => import('./AnalyseCoutsScreen'))
const InspectionsScreen = lazy(() => import('./InspectionsScreen'))
const ZonesRappelsScreen = lazy(() => import('./ZonesRappelsScreen'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'flotte',
  order: 50,
  nav: {
    label: 'FLOTTE',
    accent: 'success', // VX8 — terrain/opérations = accent success (dérivé)
    items: [
      { to: '/flotte', label: 'Cockpit', icon: <Truck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/flotte/vehicules', label: 'Véhicules & engins', icon: <Truck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/flotte/conducteurs', label: 'Conducteurs', icon: <Users size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/flotte/entretien', label: 'Entretien', icon: <Wrench size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/flotte/conformite', label: 'Conformité', icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/flotte/carburant', label: 'Carburant & télématique', icon: <Fuel size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/flotte/analyse-couts', label: 'Analyse des coûts', icon: <LineChart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/flotte/inspections', label: 'Inspections', icon: <ClipboardCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/flotte/zones-rappels', label: 'Zones & rappels', icon: <MapPin size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta — du plus spécifique au plus général (le préfixe /flotte en dernier).
  titles: [
    ['/flotte/vehicules', 'Véhicules & engins'],
    ['/flotte/conducteurs', 'Conducteurs'],
    ['/flotte/entretien', 'Entretien'],
    ['/flotte/conformite', 'Conformité'],
    ['/flotte/carburant', 'Carburant & télématique'],
    ['/flotte/analyse-couts', 'Analyse des coûts'],
    ['/flotte/inspections', 'Inspections'],
    ['/flotte/zones-rappels', 'Zones & rappels'],
    ['/flotte', 'Flotte'],
  ],
  sectionLabels: { flotte: 'Flotte' },
  routes: [
    { path: '/flotte', component: FlotteCockpit, roles: ROLES },
    { path: '/flotte/vehicules', component: VehiculesList, roles: ROLES },
    { path: '/flotte/conducteurs', component: ConducteursScreen, roles: ROLES },
    { path: '/flotte/entretien', component: EntretienScreen, roles: ROLES },
    { path: '/flotte/conformite', component: ConformiteScreen, roles: ROLES },
    { path: '/flotte/carburant', component: CarburantScreen, roles: ROLES },
    { path: '/flotte/analyse-couts', component: AnalyseCoutsScreen, roles: ROLES },
    { path: '/flotte/inspections', component: InspectionsScreen, roles: ROLES },
    { path: '/flotte/zones-rappels', component: ZonesRappelsScreen, roles: ROLES },
  ],
}

export default config
