/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Radar, FileSearch, Building2, Settings } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   VAO32 — Module frontend « Veille appels d'offres » (apps.veille_ao).
   ----------------------------------------------------------------------------
   Clé `veille_ao` IDENTIQUE au manifeste backend (VAO6, `apps/veille_ao/apps.py`
   → `module_manifest.key`) : `scripts/check_modules.py` le vérifie. `order: 58`
   — libre, juste après `ao` (57) et `adsengine` (56), même famille commerciale
   (`depends: ['ao']` côté manifeste backend).

   Trois écrans de nav, exactement ceux que le texte de VAO32 nomme : Avis ·
   Acheteurs cibles · Paramètres de veille. Le bandeau de santé (VAO37,
   `SanteVeille.jsx`) n'a PAS sa propre route — c'est un `bandeau` (bannière),
   monté EN HAUT de la liste des avis (`AvisList.jsx`), pas un écran séparé.

   Permissions (VAO12, backend) : `veille_ao_voir` — large (un Commercial doit
   voir les avis) ; `veille_ao_gerer` — palier Responsable/Directeur (mots-clés,
   sources, règles, armer la collecte). Même patron que `reporting`
   (`journal_activite_voir`) : `roles` reflète le gating large déjà en vigueur,
   `perm` porte la permission fine que le serveur vérifie réellement.

   NE JAMAIS toucher `frontend/src/features/ao/**` (réservé au Groupe AOF) — le
   rapprochement des deux sections est une tâche AOF future, pas celle-ci.
   ========================================================================== */

const AvisList = lazy(() => import('./AvisList'))
const AvisDetail = lazy(() => import('./AvisDetail'))
const AcheteursCibles = lazy(() => import('./AcheteursCibles'))
const ParametresVeille = lazy(() => import('./ParametresVeille'))

const ROLES = ['normal', 'responsable', 'admin']
const ROLES_GERER = ['responsable', 'admin']

const config = {
  key: 'veille_ao',
  order: 58,
  nav: {
    icon: appGlyph(Radar),
    label: 'VEILLE AO',
    accent: 'brass', // VX8 — croissance/commercial, même famille que ao/ventes/marketing.
    items: [
      {
        to: '/veille-ao/avis',
        label: 'Avis',
        icon: <FileSearch size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/veille-ao/acheteurs-cibles',
        label: 'Acheteurs cibles',
        icon: <Building2 size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/veille-ao/parametres',
        label: 'Paramètres de veille',
        icon: <Settings size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES_GERER,
        perm: 'veille_ao_gerer',
      },
    ],
  },
  titles: [
    ['/veille-ao/avis/', 'Veille AO — Avis'],
    ['/veille-ao/avis', 'Veille AO — Avis'],
    ['/veille-ao/acheteurs-cibles', 'Veille AO — Acheteurs cibles'],
    ['/veille-ao/parametres', 'Veille AO — Paramètres de veille'],
  ],
  sectionLabels: { 'veille-ao': 'Veille AO' },
  routes: [
    { path: '/veille-ao/avis', component: AvisList, roles: ROLES, perm: 'veille_ao_voir' },
    // Fiche avis, deep-link (pas d'item de nav dédié, même patron que
    // `/ao/affaires/:id`).
    { path: '/veille-ao/avis/:id', component: AvisDetail, roles: ROLES, perm: 'veille_ao_voir' },
    { path: '/veille-ao/acheteurs-cibles', component: AcheteursCibles, roles: ROLES, perm: 'veille_ao_voir' },
    { path: '/veille-ao/parametres', component: ParametresVeille, roles: ROLES_GERER, perm: 'veille_ao_gerer' },
  ],
}

export default config
