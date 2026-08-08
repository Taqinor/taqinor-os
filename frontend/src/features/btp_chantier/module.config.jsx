/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté
   par `router/moduleRoutes.jsx` via glob — même dérogation que
   `features/education/module.config.jsx` / `features/agriculture/
   module.config.jsx`. */
import { lazy } from 'react'
import { Construction, MapPin } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   Groupe PACT §E2 (PACT62-68) — Configuration du module « BTP / Chantier »
   (backend `apps.btp_chantier`, Groupe NTCON), auto-enregistrée. Backend
   complet et testé (7 ressources) ; ce lot pose le PREMIER frontend (aucun
   fichier n'existait avant — `key: 'btp_chantier'` matche déjà le manifeste
   backend d'`apps/btp_chantier/apps.py`, vérifié par
   `scripts/check_modules.py`).
   ----------------------------------------------------------------------------
   `order: 59` — entre veille_ao (58) et le groupe chantier/agricole (60) :
   voisin thématique naturel (`installations`, `gestion_projet`, `ao`) sans
   collision d'ordre. `accent: 'success'` — même famille que les apps
   terrain/chantier (`installations`, `agriculture`, `flotte`) ; distinct de
   ses DEUX voisins d'ordre réels (veille_ao=nuit, agriculture=success mais
   variante de teinte différente — vérifié `ui/AppIcon.voisinage.test.jsx`,
   aucune tuile jumelle adjacente). Glyphe `Construction` — distinct du
   `HardHat` déjà pris par `installations` (`lib/apps/appGlyph.test.jsx`
   interdit tout doublon).
   PACT62 pose SEULEMENT « Réserves de chantier » ; PACT63-68 ajoutent chacun
   leur écran + entrée de nav ci-dessous (surface partagée, append-only).
   ========================================================================== */

const ReservesChantierPage = lazy(() => import('./ReservesChantier'))

const ROLES = ['normal', 'responsable', 'admin']

const config = {
  key: 'btp_chantier',
  order: 59,
  nav: {
    label: 'BTP CHANTIER',
    // ODY34 — glyphe d'APP (contrat APX1 `nav.icon`), unique sur tout le
    // portail — garanti par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Construction),
    accent: 'success',
    items: [
      {
        to: '/btp-chantier/reserves',
        label: 'Réserves de chantier',
        icon: <MapPin size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
    ],
  },
  titles: [
    ['/btp-chantier/reserves', 'Réserves de chantier'],
  ],
  sectionLabels: { 'btp-chantier': 'BTP Chantier' },
  routes: [
    { path: '/btp-chantier/reserves', component: ReservesChantierPage, roles: ROLES },
  ],
}

export default config
