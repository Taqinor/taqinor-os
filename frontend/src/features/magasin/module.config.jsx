/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Warehouse, MapPin, PackageCheck, ClipboardList, Boxes, Archive } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'
// APX22 - accent unique de la famille inventaire (Stock/Magasin/Logistique).
import { INVENTAIRE_ACCENT_KEY } from '../stock/inventaireAccent'

/* ============================================================================
   MAGASIN (XSTK1) — configuration du module « Magasin » (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/magasin/` ; le registre `router/moduleRoutes.jsx`
   la collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar ni
   à routes.meta. Toutes les routes/entrées de menu sont gatées
   `['responsable','admin']` (même gating que flotte/ged/qhse — opérations
   d'entrepôt, pas un écran grand public). Écrans chargés en lazy.
   ========================================================================== */

const MagasinCockpit = lazy(() => import('./MagasinCockpit'))
const BinTreeScreen = lazy(() => import('./BinTreeScreen'))
const PutAwayScreen = lazy(() => import('./PutAwayScreen'))
const PickListScreen = lazy(() => import('./PickListScreen'))
const ColisageScreen = lazy(() => import('./ColisageScreen'))
// WIR111 — consultation référentiel & suivi entrepôt (6 familles backend-only).
const EntrepotConsultScreen = lazy(() => import('./EntrepotConsultScreen'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'magasin',
  order: 51,
  // ODY17 — métadonnées d'app pour le futur registre unifié (ODY1
  // `useInstalledApps()` / ODY9 `AppIcon.jsx`, aucun des deux livré ici).
  // ATTENTION (à noter pour ODY1/ODY26) : `magasin` n'a AUCUN manifest
  // backend (`module_manifest`, ODX2) — contrairement à `stock`/`installations`
  // — donc pas de `ModuleToggle` propre : la clé n'est jamais désactivable
  // aujourd'hui (`filterNavSections` ne masque que les clés présentes dans
  // `modules_desactives`), Magasin est un monde opérationnel de l'app Stock
  // (logistique d'entrepôt), gaté par rôle seulement. Si une future tâche en
  // fait une tuile installable à part entière, il faudra D'ABORD lui donner
  // un manifest backend (hors périmètre ODY17 : zéro nouveau modèle/app
  // backend ici).
  icon: Warehouse,
  description: "Casiers, rangement, prélèvements et colisage d'entrepôt.",
  nav: {
    label: 'MAGASIN',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Warehouse),
    // APX22 — accent de la FAMILLE INVENTAIRE (Stock/Magasin/Logistique) :
    // les trois portent la même clé, celle que Stock avait déjà. Avant, Magasin
    // et Logistique partageaient `success` avec les apps terrain/chantiers —
    // entrer dans Magasin ne ressemblait pas à entrer dans Stock.
    // Source unique : `features/stock/inventaireAccent.js`.
    accent: INVENTAIRE_ACCENT_KEY,
    items: [
      { to: '/magasin', label: 'Cockpit', icon: <Warehouse size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/magasin/casiers', label: 'Casiers', icon: <MapPin size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/magasin/rangement', label: 'Rangement (put-away)', icon: <PackageCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/magasin/prelevements', label: 'Prélèvements', icon: <ClipboardList size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/magasin/colisage', label: 'Colisage', icon: <Boxes size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/magasin/entrepot', label: 'Entrepôt (référentiel)', icon: <Archive size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta — du plus spécifique au plus général (le préfixe /magasin en dernier).
  titles: [
    ['/magasin/casiers', 'Casiers'],
    ['/magasin/rangement', 'Rangement (put-away)'],
    ['/magasin/prelevements', 'Prélèvements'],
    ['/magasin/colisage', 'Colisage'],
    ['/magasin/entrepot', 'Entrepôt (référentiel)'],
    ['/magasin', 'Magasin'],
  ],
  sectionLabels: { magasin: 'Magasin' },
  routes: [
    { path: '/magasin', component: MagasinCockpit, roles: ROLES },
    { path: '/magasin/casiers', component: BinTreeScreen, roles: ROLES },
    { path: '/magasin/rangement', component: PutAwayScreen, roles: ROLES },
    { path: '/magasin/prelevements', component: PickListScreen, roles: ROLES },
    { path: '/magasin/colisage', component: ColisageScreen, roles: ROLES },
    { path: '/magasin/entrepot', component: EntrepotConsultScreen, roles: ROLES },
  ],
}

export default config
