/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants : le
   fast-refresh ne s'y applique pas. */
import { lazy } from 'react'
import { Cpu, Search, Bot, ListChecks } from 'lucide-react'

/* ============================================================================
   ODY23 — Configuration du module « Intelligence » (IA / OCR / agent), NOUVEAU
   fichier (le module.config n'existait pas encore, `key: 'agent'` côté backend
   `apps/agent` — pas de nouvelle app Django, voir l'alias `scripts/check_modules.py`
   FRONTEND_KEY_ALIASES['ia'] = 'agent', même mécanisme que 'admin' → 'roles').
   ----------------------------------------------------------------------------
   `/ia/agent`, `/ia/ocr`, `/ia/actions` restent déclarés DIRECTEMENT dans
   `router/index.jsx` (pas encore migrés au registre — hors périmètre ODY23,
   qui ne touche pas router/index.jsx) : ce fichier ne les redéclare PAS en
   `routes` (ça dupliquerait leur enregistrement) — seule la section `nav`
   ci-dessous les référence, en attente de leur migration. SEULE route
   nouvellement déclarée ici : `/ia` (IaCockpit, ODY23), la porte d'entrée de
   l'app qui manquait — jusqu'ici OCR/Agent IA/Actions IA n'avaient aucun
   écran d'accueil commun.

   ODY4 (lane parallèle) extrait la section INTELLIGENCE encore codée en dur
   de `Sidebar.jsx:174-185` — cette `nav` est préparée pour qu'elle ait un
   endroit où atterrir (`navFor('ia')`), à l'identique des libellés/gardes de
   rôle historiques. Tant qu'ODY4 n'a pas retiré le littéral, les deux
   coexistent (attendu, résorbé au moment du fold — cf. rapport de tâche).
   ========================================================================== */

const IaCockpit = lazy(() => import('../../pages/ia/IaCockpit'))

const config = {
  key: 'ia',
  order: 65,
  nav: {
    label: 'INTELLIGENCE', labelKey: 'nav.section.intelligence',
    accent: 'lune', // VX8 — tokens.css: --module-accent-lune = « Documents/Intelligence »
    items: [
      { to: '/ia', label: 'Cockpit IA', icon: <Cpu size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['normal', 'responsable', 'admin'] },
      { to: '/ia/ocr', label: 'OCR', k: 'nav.ocr', icon: <Search size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      { to: '/ia/agent', label: 'Agent IA', k: 'nav.agent_ia', icon: <Bot size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['admin'] },
      // WIR23 — catalogue + historique/annuler des actions IA, route déjà
      // enregistrée (router/index.jsx), ouverte à tout rôle authentifié.
      { to: '/ia/actions', label: 'Actions IA', k: 'nav.agent_actions', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['normal', 'responsable', 'admin'] },
    ],
  },
  // routes.meta — /ia/ocr et /ia/agent ont déjà un titre dans
  // components/layout/routes.meta.js (BASE_PAGE_TITLES, non dupliqué ici,
  // même convention que admin/reporting/parametres) ; seul `/ia` est nouveau.
  titles: [
    ['/ia', 'Cockpit IA'],
  ],
  routes: [
    { path: '/ia', component: IaCockpit, roles: ['normal', 'responsable', 'admin'] },
  ],
}

export default config
