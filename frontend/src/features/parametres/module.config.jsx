/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import {
  MapPin, ListChecks, LayoutList, Copy, Sparkles, Settings, UserCog, Shield,
  Key, ShieldCheck, DownloadCloud, AlertTriangle, Percent, ShoppingCart, Boxes,
  Paperclip,
  Ship, Route, Factory,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   ARC54 — Migration des routes legacy Paramètres vers le registre (phase 2,
   dernière app du lot, après les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes-only pour les entrées historiques (aucune section `nav` pour elles :
   Sidebar.jsx garde son menu Administration/Paramètres hard-codé, non touché —
   `buildModuleRoutes` traite `nav` comme optionnel via `.filter(Boolean)`, donc
   « Sidebar sans doublon » tient trivialement ici). Les titres de page
   (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`) restent déjà
   déclarés là-bas pour ces chemins et ne sont PAS dupliqués ici. `/journal`
   est inclus ici (regroupé avec Paramètres dans la section ADMINISTRATION de
   Sidebar.jsx et dans le même bloc legacy de index.jsx) — aucune des 6 apps
   citées par ARC54 ne le possède plus naturellement.

   WIR13 — Territoires (`Territoires.jsx`, NTCRM3) était construit/testé mais
   monté nulle part (ni route, ni menu). `parametres` n'étant PAS l'une des 6
   clés legacy (cf. `LEGACY_NAV_KEYS` dans Sidebar.jsx), une section `nav`
   posée ici est auto-collectée par le registre générique (`moduleNavSections`,
   router/moduleRoutes.jsx) et insérée juste avant ADMINISTRATION — même
   mécanisme que `/parametres/marketing` (nav déclarée dans
   `features/marketing/module.config.jsx`).

   WIR14 — même mécanisme pour Playbooks (`Playbooks.jsx`, NTCRM13, CRUD des
   playbooks/étapes/tâches par stage STAGES.py) : construit/testé, monté nulle
   part. Deux liens dans la section `nav` ci-dessous ; les autres routes
   ci-dessus restent routes-only, comme documenté ci-dessus.

   ODY23 — « admin/roles/users/paramètres → app Paramètres » (une seule app,
   pas deux) : la section `nav` gagne ici (a) un item « Aperçu » vers le
   cockpit `/parametres` lui-même (1er item = convention `nav.items[0]` du
   cockpit, cf. `AppLauncher.jsx buildEntries`), (b) les 4 écrans réellement
   « Administration » (Utilisateurs/Rôles/Sécurité & Identité/Gouvernance des
   accès) dont la ROUTE reste déclarée dans `features/admin/module.config.jsx`
   (inchangée — un item de nav peut pointer vers une route d'un AUTRE
   module.config, même mécanisme que Journal dans `reporting`), et (c) les 3
   écrans `/parametres/*` qui avaient une route mais aucune entrée de menu
   (Export/Sauvegarde, Alertes KPI, Taxe de séjour). Gardes de rôle copiées à
   l'IDENTIQUE du littéral ADMINISTRATION historique de `Sidebar.jsx:187-209`
   (extrait par la lane ODY4, qui a besoin de cette `nav` complète pour
   atterrir). DÉLIBÉRÉMENT absent : `/admin/tenants` (console fondateur
   SCA22, superuser serveur — jamais eu d'entrée de menu, on ne l'invente pas
   ici) ; `/parametres/notifications` (atteint depuis `NotificationBell.jsx`,
   pas le menu app) ; `/parametres/marketing` (nav déjà dans
   `features/marketing/module.config.jsx`).

   PACT150 (07/08/2026) — route != menu : la garde d'atteignabilité vérifie
   désormais aussi l'entrée de nav (`nav.items[].to`/lien entrant réel/
   `// contextuelle:`), pas seulement la route. `/parametres/achats`
   (`AchatsParametresPage`, 182 lignes, WIR26) avait une route ici depuis
   ODY23 (alors notée « hors périmètre », domaine Stock/Achats lane ODY17)
   mais AUCUNE entrée de menu ni lien entrant réel n'y menait nulle part —
   un écran réel et fonctionnel, invisible. Ajouté à `nav.items` ci-dessous,
   même patron que le groupe ODY23(c).

   Gating préservé à l'identique (index.jsx:153-160 `roleLoader`) :
   - `/parametres`, `/parametres/alertes-kpi` (XPLT6) :
     `roles: ['responsable','admin']`, aucune `perm`.
   - `/parametres/export` : authLoader (aucun `roles` déclaré ci-dessous) —
     PRÉSERVÉ TEL QUEL malgré le commentaire N97 (« réservé à l'administrateur,
     l'endpoint backend exige le rôle admin ») : le loader CLIENT réel dans
     index.jsx était bien `authLoader` sans roleLoader, la garde effective est
     côté serveur.
   - `/parametres/notifications` : authLoader.
   - `/journal` : `roles: ['normal','responsable','admin']` ET
     `perm: 'journal_activite_voir'` — reflète EXACTEMENT
     `roleLoader(['normal','responsable','admin'], 'journal_activite_voir')`.
   ========================================================================== */

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const ParametresEntreprise = lazy(() => import('../../pages/parametres/ParametresEntreprise'))
const ExportSauvegarde = lazy(() => import('../../pages/parametres/ExportSauvegarde'))
const NotificationsPreferences = lazy(() => import('../../pages/parametres/NotificationsPreferences'))
// XPLT6 — CRUD des alertes de seuil sur KPI agrégés (réservé responsable/admin,
// reflète `IsResponsableOrAdmin` côté backend).
const KpiAlertesPage = lazy(() => import('../../pages/parametres/KpiAlertesPage'))
const Journal = lazy(() => import('../../pages/Journal'))
// NTMKT10 — Paramètres → Marketing : domaine d'envoi SPF/DKIM/DMARC (XMKT33).
// Composant déposé sous `features/parametres/` (pas `pages/parametres/`) —
// Files list de NTMKT10 dans docs/plans/PLAN_CRM_VENTES.md.
const DomaineEnvoi = lazy(() => import('./DomaineEnvoi'))
// NTUX23 — rapport « configuration des vues actives » (réservé responsable/
// admin, reflète `IsResponsableOrAdmin` côté backend — `toutes-company/`/
// `export-xlsx/` de SavedViewViewSet).
const VuesConfigurationPage = lazy(() => import('../../pages/parametres/VuesConfigurationPage'))
// WIR13/NTCRM3 — Territoires (règles d'affectation auto des leads entrants
// par zone/segment/secteur) — réservé responsable/admin, comme documenté en
// tête de `Territoires.jsx` (le backend applique déjà le RBAC réel).
const Territoires = lazy(() => import('./Territoires'))
// WIR14/NTCRM13 — Playbooks (CRUD des playbooks/étapes/tâches par stage) —
// même gating responsable/admin que les autres écrans de configuration CRM.
const Playbooks = lazy(() => import('./Playbooks'))
// WIR8 — Paramètres → Hôtellerie : taxe de séjour (singleton société, réservé
// responsable/admin — reflète `IsResponsableOrAdmin` côté backend).
const TaxeSejourHospitality = lazy(() => import('./TaxeSejourHospitality'))
// WIR26 — Paramètres → Achats (`stock.AchatsParametres`, singleton par
// société) : conformité (XPUR1), RAS-TVA (XPUR2), tolérances 3-voies
// (XPUR10). Écriture réservée responsable/admin (le backend applique déjà
// `stock_modifier`/legacy responsable ; lecture ouverte à tout rôle).
const AchatsParametresPage = lazy(() => import('../../pages/parametres/AchatsParametresPage'))
// WIR270/FG10 — centre de pieces jointes societe (endpoint pret, client mort).
const PiecesJointesPage = lazy(() => import('../../pages/parametres/PiecesJointesPage'))
// NTLOG36 — Paramètres → Douane (`douane.ParametresDouane`, singleton par
// société) : régime par défaut, rappels d'échéance (NTLOG22/23), mention
// estimation droits/taxes (NTLOG13/30). Écriture réservée douane_responsable
// (le backend applique déjà ScopedPermission ; lecture ouverte à tout rôle) —
// nav ET route déclarées ensemble ici (motif PACT150 : ne jamais répéter
// l'oubli de menu d'AchatsParametresPage).
const DouaneParametresPage = lazy(() => import('../../pages/parametres/DouaneParametresPage'))
// NTLOG35 — Paramètres → Transport (`transport.ParametresTransport`,
// singleton par société) : seuil d'alerte retard (NTLOG25), preuve de
// livraison obligatoire (NTLOG9), seuil anomalies d'affrètement (NTLOG28).
// Écriture réservée à un porteur de rôle (repli légataire `is_responsable` —
// le backend applique déjà `write_permission='transport_responsable'`) ;
// lecture ouverte à tout rôle interne — nav ET route déclarées ensemble
// (motif PACT150, même précédent que NTLOG36 ci-dessus).
const TransportParametresPage = lazy(() => import('../../pages/parametres/TransportParametresPage'))
// NTMFG29 — Paramètres > Atelier MRP (`mrp.ParametresMRP`, singleton par
// société) : horizon MRP (NTMFG5), stock de sécurité par défaut, tolérance de
// surcharge poste (NTMFG7), motif QC obligatoire (NTMFG13), kanban production
// (NTMFG17). Admin UNIQUEMENT côté backend (`mrp.permissions.EstAdminMRP`) —
// un Responsable planifie (NTMFG3) mais ne voit/modifie pas ces réglages ; nav
// ET route déclarées ensemble (motif PACT150, même précédent que NTLOG35/36).
const MrpParametresPage = lazy(() => import('../../pages/mrp/ParametresMRP'))
// WIR152 — Paramètres → Doublons tiers (`tiers.TiersViewSet.doublons`,
// ARC20, admin-only côté backend — même gating ici).
const TiersDoublonsPage = lazy(() => import('../../pages/parametres/TiersDoublonsPage'))
// WIR153 — Paramètres → IA : panneau de diagnostic (provider/modèle LLM actif
// + tables autorisées de l'agent SQL, GET /sql-agent/schema — jusqu'ici sans
// appelant côté frontend). Admin-only (écran de configuration sensible).
const IaDiagnostic = lazy(() => import('./IaDiagnostic'))
// PACT140 — Objets métier personnalisés (XPLT16) : définition sans code d'un
// objet + de ses champs (mécanisme CustomFieldDef EXISTANT pointé sur
// `module: custom:<code>`), puis écran GÉNÉRIQUE de ses enregistrements rendu
// à partir des schémas auto-générés (NTEXT2 vue-liste / NTEXT3 vue-formulaire).
// Admin-only côté objets/champs (le backend applique `IsAdminRole`).
const ObjetsPersonnalisesPage = lazy(() => import('./ObjetsPersonnalisesPage'))
const CustomObjectRecordsPage = lazy(() => import('../customobjects/CustomObjectRecordsPage'))

const config = {
  key: 'parametres',
  order: 90,
  nav: {
    label: 'PARAMÈTRES',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Settings),
    accent: 'nuit',
    items: [
      // ODY23(a) — cockpit de l'app (1er item = lien du cockpit).
      { to: '/parametres', label: 'Aperçu', icon: <Settings size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      // ODY23(b) — Administration (route déclarée dans features/admin/module.config.jsx).
      { to: '/admin/users', label: 'Utilisateurs', icon: <UserCog size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      { to: '/admin/roles', label: 'Rôles', icon: <Shield size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      { to: '/admin/securite-identite', label: 'Sécurité & Identité', icon: <Key size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['admin'] },
      { to: '/admin/gouvernance-acces', label: 'Gouvernance des accès', icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['admin'] },
      { to: '/parametres/territoires', label: 'Territoires', icon: <MapPin size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      { to: '/parametres/playbooks', label: 'Playbooks', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      {
        to: '/parametres/vues',
        label: 'Vues sauvegardées',
        icon: <LayoutList size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['responsable', 'admin'],
      },
      { to: '/parametres/tiers-doublons', label: 'Doublons tiers', icon: <Copy size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['admin'] },
      { to: '/parametres/ia', label: 'IA (diagnostic)', icon: <Sparkles size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['admin'] },
      // ODY23(c) — écrans /parametres/* qui avaient une route sans entrée de menu.
      { to: '/parametres/export', label: 'Export / Sauvegarde', icon: <DownloadCloud size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['admin'] },
      // WIR270 — centre de pieces jointes (isolation societe garantie serveur).
      { to: '/parametres/pieces-jointes', label: 'Pièces jointes', icon: <Paperclip size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      { to: '/parametres/alertes-kpi', label: 'Alertes KPI', icon: <AlertTriangle size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      { to: '/parametres/hospitality/taxe-sejour', label: 'Taxe de séjour', icon: <Percent size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      // PACT150 — même défaut que ODY23(c) : route déclarée (WIR26), aucune
      // entrée de menu, écran réel de 182 lignes invisible pour toujours.
      { to: '/parametres/achats', label: 'Achats', icon: <ShoppingCart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      // NTLOG36 — nav ET route ensemble (voir commentaire du lazy import ci-dessus).
      { to: '/parametres/douane', label: 'Douane', icon: <Ship size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      // NTLOG35 — nav ET route ensemble (voir commentaire du lazy import ci-dessus).
      { to: '/parametres/transport', label: 'Transport', icon: <Route size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      // NTMFG29 — Admin uniquement (voir commentaire du lazy import ci-dessus).
      { to: '/parametres/mrp', label: 'Atelier MRP', icon: <Factory size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['admin'] },
      // PACT140 — Objets métier personnalisés (l'écran des enregistrements
      // `/objets/:code` s'atteint depuis cette page, un lien par objet).
      { to: '/parametres/objets-personnalises', label: 'Objets personnalisés', icon: <Boxes size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['admin'] },
    ],
  },
  routes: [
    { path: '/parametres', component: ParametresEntreprise, roles: ['responsable', 'admin'] },
    { path: '/parametres/export', component: ExportSauvegarde },
    { path: '/parametres/notifications', component: NotificationsPreferences },
    { path: '/parametres/alertes-kpi', component: KpiAlertesPage, roles: ['responsable', 'admin'] },
    { path: '/parametres/marketing', component: DomaineEnvoi, roles: ['responsable', 'admin'] },
    { path: '/parametres/vues', component: VuesConfigurationPage, roles: ['responsable', 'admin'] },
    { path: '/parametres/territoires', component: Territoires, roles: ['responsable', 'admin'] },
    { path: '/parametres/playbooks', component: Playbooks, roles: ['responsable', 'admin'] },
    { path: '/parametres/hospitality/taxe-sejour', component: TaxeSejourHospitality, roles: ['responsable', 'admin'] },
    { path: '/parametres/achats', component: AchatsParametresPage, roles: ['responsable', 'admin'] },
    { path: '/parametres/pieces-jointes', component: PiecesJointesPage, roles: ['responsable', 'admin'] },
    { path: '/parametres/douane', component: DouaneParametresPage, roles: ['responsable', 'admin'] },
    { path: '/parametres/transport', component: TransportParametresPage, roles: ['responsable', 'admin'] },
    { path: '/parametres/mrp', component: MrpParametresPage, roles: ['admin'] },
    { path: '/parametres/tiers-doublons', component: TiersDoublonsPage, roles: ['admin'] },
    { path: '/parametres/ia', component: IaDiagnostic, roles: ['admin'] },
    { path: '/parametres/objets-personnalises', component: ObjetsPersonnalisesPage, roles: ['admin'] },
    // Segment dynamique : un SEUL écran générique sert tous les objets. Atteint
    // depuis /parametres/objets-personnalises (un lien « Enregistrements » par
    // objet) — la lecture d'un enregistrement reste ouverte aux rôles autorisés
    // par la permission `custom_object.<code>.voir` côté serveur.
    { path: '/objets/:code', component: CustomObjectRecordsPage },
    {
      path: '/journal',
      component: Journal,
      roles: ['normal', 'responsable', 'admin'],
      perm: 'journal_activite_voir',
    },
  ],
}

export default config
