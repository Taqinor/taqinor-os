/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Compass } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   PACT122 — configuration du module « Données » (surfaces du SOCLE).
   ----------------------------------------------------------------------------
   Point de montage des écrans qui exposent des capacités de FONDATION (`core`)
   et n'appartiennent à aucun domaine métier. Sans ce fichier, un écran livré
   sous `features/core/` resterait injoignable — c'est exactement la dette que
   `scripts/check_ecrans_atteignables.py` interdit désormais.

   Clé `core` = la clé du manifeste backend `core/apps.py` (contrat
   `scripts/check_modules.py`). Le manifeste est `installable: False` : cette
   fondation n'est jamais désactivable, donc le gating par module (ODX6) ne la
   masque jamais — cohérent avec une surface transverse.

   Chemin dédié `/donnees/*` : premier segment libre (aucun autre module ne le
   prend), et `routes.meta` résout par le PREMIER préfixe correspondant.

   Gaté `responsable`/`admin` : l'explorateur lit des jeux de données transverses
   de la société.
   ========================================================================== */

const ROLES = ['responsable', 'admin']

const ExplorateurDonneesPage = lazy(() => import('./ExplorateurDonneesPage'))

const config = {
  key: 'core',
  order: 94,
  nav: {
    label: 'DONNÉES',
    // ODY34 — glyphe d'APP unique sur tout le portail (garanti par
    // `lib/apps/appGlyph.test.jsx`) : `Compass` = explorer ses données.
    icon: appGlyph(Compass),
    // PACT122 fix — `info` n'est pas une voie `--app-tile-*` déclarée dans
    // design/tokens.css (voir la liste : brass/warning/destructive/success/
    // azur/lune/nuit/primary). `accent: 'info'` rendait une tuile SANS fond
    // (var() invalide) — exactement le piège que `AppIcon.voisinage.test.jsx`
    // existe pour détecter. `azur` est la voie la plus proche du sens
    // recherché (explorateur de données = information).
    accent: 'azur',
    items: [
      {
        to: '/donnees/explorateur',
        label: 'Explorateur',
        icon: <Compass size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
    ],
  },
  titles: [
    ['/donnees/explorateur', 'Explorateur de données'],
  ],
  sectionLabels: { donnees: 'Données' },
  routes: [
    {
      path: '/donnees/explorateur',
      component: ExplorateurDonneesPage,
      roles: ROLES,
    },
  ],
}

export default config
