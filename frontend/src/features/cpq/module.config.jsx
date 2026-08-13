/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Blocks, Wand2 } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   PACT125 — configuration du module « CPQ » (auto-enregistrée).
   ----------------------------------------------------------------------------
   Le backend `apps/cpq` pilotait un configurateur guidé complet (NTCPQ9/10 :
   session questions-réponses → produits/bundles résolus par le moteur de
   règles → devis brouillon) SANS aucun fichier frontend : le dossier
   `features/cpq/` n'existait pas. Ce fichier est le point de montage du
   module — sans lui, tout écran CPQ livré resterait injoignable
   (`scripts/check_ecrans_atteignables.py`).

   Clé `cpq` = la clé du manifeste backend `apps/cpq/apps.py` (contrat
   `scripts/check_modules.py`) : aucun alias nécessaire.

   Chemins dédiés `/cpq/*` : premier segment libre, aucun autre module ne le
   prend, et `routes.meta` résout par le PREMIER préfixe correspondant — les
   titres vont donc du plus spécifique au plus général.

   Gaté `responsable`/`admin` : le configurateur crée des devis brouillons et
   son onglet « Questions » est du paramétrage (le backend applique le même
   palier — `IsResponsableOrAdmin` en écriture).
   ========================================================================== */

const ROLES = ['responsable', 'admin']

const ConfigurateurPage = lazy(() => import('./ConfigurateurPage'))

const config = {
  key: 'cpq',
  order: 21, // juste après Ventes/Stock — même famille commerciale.
  nav: {
    label: 'CPQ',
    // ODY34 — glyphe d'APP unique sur tout le portail (garanti par
    // `lib/apps/appGlyph.test.jsx`) : `Blocks` = assembler une configuration.
    icon: appGlyph(Blocks),
    accent: 'primary',
    items: [
      {
        to: '/cpq/configurateur',
        label: 'Configurateur',
        icon: <Wand2 size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
    ],
  },
  titles: [
    ['/cpq/configurateur', 'Configurateur guidé'],
  ],
  sectionLabels: { cpq: 'CPQ' },
  routes: [
    { path: '/cpq/configurateur', component: ConfigurateurPage, roles: ROLES },
  ],
}

export default config
