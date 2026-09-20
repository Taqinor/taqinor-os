/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `features/ao`). */
import { lazy } from 'react'
import { Grid3x3, LayoutGrid, PlusCircle } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   CAL34 — LA PORTE AUTONOME du module Calepinage.
   ----------------------------------------------------------------------------
   DÉCISION FONDATEUR (Reda, 19/09/2026, n°3, verbatim) : « the new calpinage
   module should work exactly the same as it is right now in the CRM just have
   more features. and of course we can access it from the standalone module, and
   pick whatever client or lead and make its calpinage. »

   D3 — cette porte N'EXISTE PAS aujourd'hui : le seul accès au calepinage passe
   par un devis (`router/index.jsx`) ou par une affaire AO
   (`features/ao/module.config.jsx`). Ce module est une porte SUPPLÉMENTAIRE,
   jamais un remplacement : aucune ligne de `LeadWorkspace.jsx` ni du mode
   `devis` de `ToitureDesign.jsx` n'est touchée par cette lane.

   `key: 'calepinage'` — IDENTIQUE au `module_manifest` backend posé par CAL4
   (`apps/calepinage/apps.py`). C'est l'ancrage de corrélation vérifié par
   `scripts/check_modules.py` ET la clé que `router/moduleRoutes.jsx` propage
   automatiquement vers `router/moduleGating.js` : module éteint pour la société
   ⇒ zéro entrée de nav et routes en 404, sans aucun tableau à tenir à la main.

   `order: 98` — 97 est le maximum occupé par un `module.config.jsx` du dépôt au
   moment de cette lane (vérifié), 98 est donc libre ; une collision d'`order`
   est attrapée par le test de registre existant.

   `nav.icon` (ODY34) — `Grid3x3`, le quadrillage des modules posés sur un pan
   de toit. Glyphe UNIQUE sur tout le portail : `lib/apps/appGlyph.test.jsx`
   interdit tout doublon, et `LayoutGrid` (déjà porté par un ITEM de nav d'AO)
   reste réservé à l'item de liste ci-dessous, jamais au glyphe d'app.

   ORDRE DES ROUTES — `/calepinage/nouveau` est déclarée AVANT `/calepinage/:id`.
   Inversées, « nouveau » serait capté comme un identifiant de calepinage et
   l'écran de création deviendrait injoignable (exactement le piège documenté
   sur `/ao/affaires/nouveau`).
   ========================================================================== */

const ROLES = ['normal', 'responsable', 'admin']

/* ── L'ATELIER 3D DU CALEPINAGE — le MÊME builder, un quatrième mode ───────
   `pages/ventes/ToitureDesign` héberge déjà le builder 3D et sert les modes
   `lead`, `devis` et `ao` sur le MÊME écran ; le mode `calepinage` (CAL37, lane
   `frontend/atelier`) le réutilise tel quel sur un CALEPINAGE. Une seconde
   implémentation de la toiture 3D serait la garantie de deux calepinages qui
   divergent — c'est le raisonnement déjà écrit dans `features/ao`.
   `buildModuleRoutes` monte `<Comp />` SANS props : le mode est donc figé par
   cette enveloppe lazy, exactement comme le fait AO pour `mode="ao"`. */
const AtelierCalepinage = lazy(async () => {
  const { default: ToitureDesign } = await import('../../pages/ventes/ToitureDesign')
  return { default: () => <ToitureDesign mode="calepinage" /> }
})

// CAL35 — la LISTE réelle : vignettes, filtres RÉELLEMENT servis par CAL16,
// pagination et état vide qui explique le geste de création.
const CalepinageList = lazy(() => import('./CalepinageList'))
// CAL36 — l'écran de CRÉATION : choisir un lead OU un client, recherche bornée
// société côté serveur, contexte géographique lu et jamais deviné.
const CalepinageNouveau = lazy(() => import('./CalepinageNouveau'))

const config = {
  key: 'calepinage',
  order: 98,
  nav: {
    icon: appGlyph(Grid3x3),
    label: 'CALEPINAGE',
    // Même famille visuelle que les modules métier solaires (ventes, AO).
    accent: 'brass',
    items: [
      {
        to: '/calepinage',
        label: 'Calepinages',
        icon: <LayoutGrid size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/calepinage/nouveau',
        label: 'Nouveau calepinage',
        icon: <PlusCircle size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
    ],
  },
  // `titles` — correspondance par PRÉFIXE, du plus spécifique au plus général.
  titles: [
    ['/calepinage/nouveau', 'Calepinage — Nouveau calepinage'],
    ['/calepinage/', 'Calepinage — Atelier'],
    ['/calepinage', 'Calepinage — Calepinages'],
  ],
  sectionLabels: { calepinage: 'Calepinage' },
  routes: [
    { path: '/calepinage', component: CalepinageList, roles: ROLES },
    // AVANT `/calepinage/:id` — sinon « nouveau » est lu comme un identifiant.
    { path: '/calepinage/nouveau', component: CalepinageNouveau, roles: ROLES },
    // Atelier d'UN calepinage — deep-link, jamais un item de nav : il est
    // contextuel à un objet, comme `/ao/affaires/:id/design`. C'est la cible de
    // la redirection après création (CAL36).
    { path: '/calepinage/:id', component: AtelierCalepinage, roles: ROLES },
  ],
}

export default config
