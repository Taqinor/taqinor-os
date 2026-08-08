/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un
   module de composants : le fast-refresh ne s'y applique pas (cf. router/
   moduleRoutes, même dérogation que tous les autres module.config.jsx). */
import { lazy } from 'react'
import { DoorOpen } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   PACT96 — module.config.jsx de l'app « Portail client » (première création :
   `apps/portail` n'avait encore AUCUN écran ERP interne — le portail CLIENT
   lui-même vit hors de ce registre, monté directement dans
   `router/index.jsx` sous `/portail/client|fournisseur|partenaire` avec son
   propre shell `WithPortal` — voir la note ci-dessous).
   ----------------------------------------------------------------------------
   Trou couvert par PACT96-101 (§E3, docs/PLAN.md) : `apps.portail` a un
   backend entier et testé (comptes d'accès, preuve d'acceptation de devis,
   paiements en ligne, documents client, jalons de chantier, demandes de
   ticket SAV) mais AUCUN écran ERP interne pour l'ADMINISTRER — seul le
   client final voit son propre espace. Une SEULE app/route/entrée de nav
   (« Portail client — Administration »), à onglets (PortailAdminPage) : les
   6 ressources y sont montées une par une par PACT96-101, cf. ce fichier lui-
   même n'a pas besoin d'être retouché à chaque tâche suivante (un seul
   `nav.items`/une seule `routes:` suffit pour tout l'écran à onglets).

   ATTENTION — NE PAS CONFONDRE avec `/portail/client`, `/portail/fournisseur`,
   `/portail/partenaire` : ces trois routes sont le portail SELF-SERVICE
   externe (comptes `portail_client`/`portail_fournisseur`/`portail_partenaire`),
   déclarées en dur dans `router/index.jsx` avec leur propre garde
   `portalLoader` et leur propre shell (jamais le layout ERP, jamais ce
   registre de module). La route ci-dessous (`/portail/administration`) est un
   écran ERP INTERNE, gardé comme toute autre route interne (`roleLoader`,
   layout ERP) — un chemin volontairement distinct pour ne jamais laisser
   croire qu'il s'agit du même espace.

   ODY34 — glyphe et accent DISTINCTS de tout voisin du registre (gardés par
   `lib/apps/appGlyph.test.jsx` et `ui/AppIcon.voisinage.test.jsx`) : `order:
   41` place Portail juste après CRM (40)/RH (40, tous deux accent `azur`) et
   avant Flotte (50, accent `success`) — `lune` (référentiel documentaire/
   accès, même famille que GED/KB/IA) ne collisionne avec aucun des deux
   voisins immédiats. `DoorOpen` (porte d'accès — la métaphore du portail)
   n'est repris comme glyphe D'APP par aucun autre module (déjà utilisé comme
   icône de SOUS-ÉCRAN dans `features/hospitality/module.config.jsx`, ce qui
   ne compte pas pour ce garde-fou — seul `nav.icon` est comparé). */

const PortailAdminPage = lazy(() => import('./admin/PortailAdminPage'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'portail',
  order: 41,
  nav: {
    label: 'PORTAIL CLIENT',
    icon: appGlyph(DoorOpen),
    accent: 'lune',
    items: [
      {
        to: '/portail/administration',
        label: 'Administration',
        icon: <DoorOpen size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
    ],
  },
  titles: [
    ['/portail/administration', 'Portail client — Administration'],
  ],
  sectionLabels: { portail: 'Portail client' },
  routes: [
    { path: '/portail/administration', component: PortailAdminPage, roles: ROLES },
  ],
}

export default config
