import { lazy, Suspense, useMemo } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  LayoutDashboard, MessageSquare, Package, Boxes, Truck, ArrowLeftRight,
  ClipboardList, PackageCheck, FileText, Undo2, ScanLine, Users, Target, Map,
  UserPlus, ShoppingCart, Receipt, FileMinus, Wallet, CalendarClock,
  CalendarDays, HardHat, Wrench, Cpu, BarChart3, Search, Bot, UserCog, Shield,
  ScrollText, Settings, DownloadCloud, LogOut, ChevronLeft, ChevronRight, Key,
  Briefcase, User as UserIcon, FolderOpen, Inbox, AlertTriangle, Tv,
} from 'lucide-react'
import { logoutUser } from '../../features/auth/store/authSlice'
// UX1 — Sections de navigation des modules « coquille », enregistrées par
// chaque module via `features/<module>/module.config.jsx` (aucun couplage ici).
import { moduleNavSections } from '../../router/moduleRoutes'
// N93 — libellés de la coquille traduits (nav + sections). FR = repli.
import { useT } from '../../i18n'
// VX86 — compteur partagé des approbations en attente (badge nav discret).
import { useApprobationsCount } from '../../hooks/useApprobationsCount'
// VX247(c) — même hook PARTAGÉ que la bannière Dashboard (VX36) et l'onglet
// Paramètres « Prise en main » : une seule dérivation de la progression.
import { useOnboardingSteps } from '../../features/onboarding/onboardingHelpers'
// VX58 — préchargement au survol/focus des destinations chaudes (même source
// d'imports dynamiques que le routeur ; no-op sous Data Saver/2G).
import { prefetchRoute } from '../../router/prefetchMap'
// ODX6 — gating par module actif/désactivé (source unique = /auth/me/).
import { filterNavSections, selectModulesDesactives } from '../../router/moduleGating'
// VX157 — pastille d'impact du parc (production + CO₂ évité cumulés),
// chargée PARESSEUSEMENT : le composant fait son propre appel API et rend
// null tant que rien n'est disponible, donc aucun coût/flash pour les écrans
// qui n'ont jamais de données de parc.
const ImpactPastille = lazy(() => import('./ImpactPastille'))
// VX10 — bande d'apps épinglées personnelles, sous le badge de rôle.
const PinnedApps = lazy(() => import('./PinnedApps'))

// FG16 — ancres du guide d'accueil : map `to` → valeur `data-coach` posée sur
// le lien correspondant, pour que le spotlight des coachmarks puisse le cibler.
// VX247(a) — `ma-file` ancre la nouvelle étape non-admin (STEPS d'OnboardingCoachmarks).
const COACH_ANCHORS = {
  '/stock': 'produits',
  '/parametres': 'parametres',
  '/admin/users': 'equipe',
  '/activites': 'ma-file',
}

// ── P168 — Système d'icônes unifié (lucide-react) ─────────────────────────────
// Toutes les icônes de la coquille viennent désormais d'une seule librairie, à
// une épaisseur (1.75) et des tailles standardisées issues de l'échelle 3.5/4/5
// (14 / 16 / 20 px). Plus aucun SVG dessiné à la main : géométrie, alignement et
// poids de trait sont cohérents partout. `aria-hidden` car le libellé textuel
// porte déjà l'accessibilité.
const ICON_MD = 17     // ~4 (16–18 px) — items de navigation
const ICON_SM = 13     // ~3.5 (14 px)  — badges de rôle (denses)
const STROKE = 1.75
const mk = (Comp, size = ICON_MD) => (
  <Comp size={size} strokeWidth={STROKE} aria-hidden="true" />
)

const I = {
  dashboard:    mk(LayoutDashboard),
  produits:     mk(Package),
  mouvements:   mk(ArrowLeftRight),
  ocr_import:   mk(ScanLine),
  clients:      mk(Users),
  leads:        mk(Target),
  devis:        mk(FileText),
  bons_cmd:     mk(ShoppingCart),
  factures:     mk(Receipt),
  wallet:       mk(Wallet),
  ocr:          mk(Search),
  agent_ia:     mk(Bot),
  reporting:    mk(BarChart3),
  utilisateurs: mk(UserCog),
  parametres:   mk(Settings),
  logout:       mk(LogOut),
  chevL:        mk(ChevronLeft),
  chevR:        mk(ChevronRight),
  key:          mk(Key, ICON_SM),
  roles_icon:   mk(Shield),
  briefcase:    mk(Briefcase, ICON_SM),
  user_single:  mk(UserIcon, ICON_SM),
  chantiers:    mk(HardHat),
  demandes_achat: mk(ClipboardList),
  outillage:    mk(Wrench),
  equipements:  mk(Boxes),
  sav:          mk(Wrench),
  agenda:       mk(CalendarClock),
  calendrier:   mk(CalendarDays),
  carte:        mk(Map),
  journal:      mk(ScrollText),
  messages:     mk(MessageSquare),
  fournisseurs: mk(Truck),
  cmd_fourn:    mk(ClipboardList),
  reception:    mk(PackageCheck),
  retour:       mk(Undo2),
  parrainage:   mk(UserPlus),
  avoir:        mk(FileMinus),
  production:   mk(BarChart3),
  export:       mk(DownloadCloud),
  cpu:          mk(Cpu),
  documents:    mk(FolderOpen),
  approbations: mk(Inbox),
  alertes_kpi:  mk(AlertTriangle),
  dashboards_tv: mk(Tv),
}

const ROLE_META = {
  admin:       { label: 'Administrateur', icon: I.key },
  responsable: { label: 'Responsable',    icon: I.briefcase },
  normal:      { label: 'Utilisateur',    icon: I.user_single },
}

// N93 — chaque libellé porte une clé i18n `k` (nav.*) et chaque section une
// `labelKey` (nav.section.*). Le libellé FR reste en dur comme REPLI (rendu
// identique quand locale=fr, et si une clé venait à manquer).
// VX8 — accent de module par section : une des 7 clés `--module-accent-*` de
// tokens.css (dérivées des rampes/couleurs existantes, aucune inventée).
// `accent: null` (première section, sans label) reste neutre.
// VX12 — exportée en plus de l'usage local : le sélecteur mobile « Plus »
// (BottomTabBar.jsx) réutilise la MÊME liste que la Sidebar desktop (aucune
// duplication), seule la présentation change (grille par catégorie). L'export
// d'une constante partagée est délibéré (react-refresh est une règle de DX
// hot-reload, pas de correction) — d'où le disable ciblé ci-dessous.
// eslint-disable-next-line react-refresh/only-export-components
export const NAV_SECTIONS = [
  {
    label: null,
    accent: null,
    items: [
      { to: '/dashboard',            label: 'Dashboard',        k: 'nav.dashboard',  icon: I.dashboard,    roles: ['normal','responsable','admin'] },
      // VX83 — « Ma file » : LA file de travail unique cross-module, promue
      // hors de CRM vers le groupe de tête (route /activites préservée pour
      // ne casser ni le routing ni les hooks e2e).
      { to: '/activites',            label: 'Ma file',          k: 'nav.activites',  icon: I.agenda,       roles: ['normal','responsable','admin'] },
      { to: '/messages',             label: 'Messages',         k: 'nav.messages',   icon: I.messages,     roles: ['normal','responsable','admin'] },
    ],
  },
  {
    // ODX6 — clé de module pour le gating nav/route (masqué si désactivé pour
    // la société). Absence de toggle ⇒ affiché comme aujourd'hui.
    key: 'stock',
    label: 'STOCK', labelKey: 'nav.section.stock',
    accent: 'lune',
    items: [
      { to: '/stock',                label: 'Produits',         k: 'nav.produits',   icon: I.produits,     roles: ['normal','responsable','admin'] },
      { to: '/stock/categories',     label: 'Catégories & marques', k: 'nav.categories', icon: I.equipements, roles: ['responsable','admin'] },
      { to: '/stock/fournisseurs',   label: 'Fournisseurs',     k: 'nav.fournisseurs', icon: I.fournisseurs, roles: ['responsable','admin'] },
      { to: '/stock/mouvements',     label: 'Mouvements',       k: 'nav.mouvements', icon: I.mouvements,   roles: ['normal','responsable','admin'] },
      { to: '/stock/bons-commande-fournisseur', label: 'Commandes fournisseur', k: 'nav.commandes_fournisseur', icon: I.cmd_fourn, roles: ['responsable','admin'] },
      { to: '/stock/modeles-bcf',    label: 'Modèles de commande', k: 'nav.modeles_bcf', icon: I.cmd_fourn,    roles: ['responsable','admin'] },
      { to: '/stock/receptions-fournisseur', label: 'Réceptions fournisseur', k: 'nav.receptions_fournisseur', icon: I.reception, roles: ['responsable','admin'] },
      { to: '/stock/factures-fournisseur', label: 'Factures fournisseur', k: 'nav.factures_fournisseur', icon: I.factures, roles: ['responsable','admin'] },
      { to: '/stock/retours-fournisseur', label: 'Retours fournisseur', k: 'nav.retours_fournisseur', icon: I.retour, roles: ['responsable','admin'] },
      { to: '/stock/ocr-import',     label: 'Import OCR',       k: 'nav.import_ocr', icon: I.ocr_import,   roles: ['responsable','admin'] },
    ],
  },
  {
    key: 'crm',
    label: 'CRM', labelKey: 'nav.section.crm',
    accent: 'azur',
    items: [
      { to: '/calendrier',           label: 'Calendrier',       k: 'nav.calendrier', icon: I.calendrier,   roles: ['normal','responsable','admin'] },
      { to: '/crm',                  label: 'Clients',          k: 'nav.clients',    icon: I.clients,      roles: ['normal','responsable','admin'] },
      { to: '/crm/leads',            label: 'Leads',            k: 'nav.leads',      icon: I.leads,        roles: ['normal','responsable','admin'] },
      { to: '/carte',                label: 'Carte',            k: 'nav.carte',      icon: I.carte,        roles: ['normal','responsable','admin'] },
      { to: '/crm/parrainage',       label: 'Parrainage',       k: 'nav.parrainage', icon: I.parrainage,   roles: ['normal','responsable','admin'] },
    ],
  },
  {
    key: 'ventes',
    label: 'VENTES', labelKey: 'nav.section.ventes',
    accent: 'brass',
    items: [
      { to: '/ventes/devis',         label: 'Devis',            k: 'nav.devis',      icon: I.devis,        roles: ['normal','responsable','admin'] },
      { to: '/ventes/bons-commande', label: 'Bons de commande', k: 'nav.bons_commande', icon: I.bons_cmd,  roles: ['normal','responsable','admin'] },
      { to: '/ventes/factures',      label: 'Factures',         k: 'nav.factures',   icon: I.factures,     roles: ['normal','responsable','admin'] },
      { to: '/ventes/avoirs',        label: 'Avoirs',           k: 'nav.avoirs',     icon: I.avoir,        roles: ['normal','responsable','admin'] },
      { to: '/ventes/paiements',     label: 'Encaissements',    k: 'nav.encaissements', icon: I.wallet,    roles: ['normal','responsable','admin'] },
      { to: '/ventes/relances',      label: 'Relances / Impayés', k: 'nav.relances', icon: I.agenda,      roles: ['responsable','admin'] },
    ],
  },
  {
    key: 'installations',
    label: 'CHANTIERS', labelKey: 'nav.section.chantiers',
    accent: 'success',
    items: [
      { to: '/ma-journee',           label: 'Ma journée',       k: 'nav.ma_journee', icon: I.agenda,       roles: ['normal','responsable','admin'] },
      { to: '/chantiers',            label: 'Chantiers',        k: 'nav.chantiers',  icon: I.chantiers,    roles: ['normal','responsable','admin'] },
      { to: '/chantiers/demandes-achat', label: "Demandes d'achat", k: 'nav.demandes_achat', icon: I.demandes_achat, roles: ['normal','responsable','admin'] },
      { to: '/interventions',        label: 'Interventions',    k: 'nav.interventions', icon: I.outillage, roles: ['normal','responsable','admin'] },
      { to: '/planification',        label: 'Planification',    k: 'nav.planification', icon: I.agenda,    roles: ['normal','responsable','admin'] },
      { to: '/parc',                 label: 'Parc installé',    k: 'nav.parc',       icon: I.equipements,  roles: ['normal','responsable','admin'] },
      { to: '/atelier',              label: 'Atelier',          k: 'nav.atelier',    icon: I.outillage,    roles: ['normal','responsable','admin'] },
      { to: '/production',           label: 'Production',       k: 'nav.production', icon: I.production,   roles: ['normal','responsable','admin'] },
      { to: '/outillage',            label: 'Outillage',        k: 'nav.outillage',  icon: I.outillage,    roles: ['normal','responsable','admin'] },
    ],
  },
  {
    key: 'sav',
    label: 'APRÈS-VENTE', labelKey: 'nav.section.apres_vente',
    accent: 'destructive',
    items: [
      { to: '/equipements',          label: 'Équipements',      k: 'nav.equipements', icon: I.equipements, roles: ['normal','responsable','admin'] },
      { to: '/sav',                  label: 'Tickets SAV',      k: 'nav.tickets_sav', icon: I.sav,         roles: ['normal','responsable','admin'] },
      { to: '/sav/contrats',         label: 'Contrats maintenance', k: 'nav.contrats_maintenance', icon: I.sav, roles: ['responsable','admin'] },
      { to: '/sav/warranty-claims',  label: 'Garanties fournisseur (RMA)', k: 'nav.warranty_claims', icon: I.sav, roles: ['responsable','admin'] },
      { to: '/sav/kb',               label: 'Base de connaissances SAV', k: 'nav.sav_kb', icon: I.sav, roles: ['normal','responsable','admin'] },
      { to: '/sav/alarmes',          label: 'Alarmes onduleur',  k: 'nav.sav_alarmes', icon: I.sav, roles: ['normal','responsable','admin'] },
      { to: '/sav/action-requise',   label: 'Action requise',    k: 'nav.sav_action_requise', icon: I.sav, roles: ['responsable','admin'] },
      { to: '/sav/sla-rapport',      label: 'Rapport SLA SAV',   k: 'nav.sav_sla_rapport', icon: I.sav, roles: ['responsable','admin'] },
      { to: '/sav/parametres',       label: 'Paramètres SAV',    k: 'nav.sav_parametres', icon: I.sav, roles: ['responsable','admin'] },
    ],
  },
  {
    key: 'ged',
    label: 'DOCUMENTS', labelKey: 'nav.section.documents',
    accent: 'lune',
    items: [
      { to: '/ged',                  label: 'Documents (GED)',  k: 'nav.documents_ged', icon: I.documents, roles: ['normal','responsable','admin'] },
    ],
  },
  {
    label: 'INTELLIGENCE', labelKey: 'nav.section.intelligence',
    accent: 'lune',
    items: [
      { to: '/ia/ocr',               label: 'OCR',              k: 'nav.ocr',        icon: I.ocr,          roles: ['responsable','admin'] },
      { to: '/ia/agent',             label: 'Agent IA',         k: 'nav.agent_ia',   icon: I.agent_ia,     roles: ['admin'] },
    ],
  },
  {
    key: 'reporting',
    label: 'ANALYSE', labelKey: 'nav.section.analyse',
    accent: 'warning',
    items: [
      { to: '/reporting',            label: 'Reporting',        k: 'nav.reporting',  icon: I.reporting,    roles: ['responsable','admin'] },
      { to: '/rapports',             label: 'Rapports',         k: 'nav.rapports',   icon: I.reporting,    roles: ['responsable','admin'] },
      { to: '/reporting/balance-agee', label: 'Balance âgée',   k: 'nav.balance_agee', icon: I.reporting,  roles: ['responsable','admin'] },
      { to: '/reporting/commercial', label: 'Tableau commercial', k: 'nav.tableau_commercial', icon: I.reporting, roles: ['responsable','admin'] },
      // XKB1/ZCTR7-9 — boîte d'approbations centralisée, ouverte à tout rôle
      // (chacun peut avoir des demandes en attente sur son périmètre).
      { to: '/approbations',         label: 'Approbations',     k: 'nav.approbations', icon: I.approbations, roles: ['normal','responsable','admin'] },
      // XPLT22 — classeurs (mini-tableurs BI avec données live).
      { to: '/reporting/classeurs',  label: 'Classeurs',        k: 'nav.classeurs',  icon: I.reporting,    roles: ['responsable','admin'] },
      // XSAV8 — conformité SLA + KPI SAV avancés.
      { to: '/reporting/sav-sla',    label: 'SLA SAV',          k: 'nav.sav_sla',    icon: I.reporting,    roles: ['responsable','admin'] },
      // XFSM16 — analytics field service consolidés (FTF, MTTR, ponctualité…).
      { to: '/reporting/field-service', label: 'Analytics terrain', k: 'nav.field_service', icon: I.reporting, roles: ['responsable','admin'] },
      // XFSM17 — scorecard coaching par technicien vs moyenne équipe.
      { to: '/reporting/scorecard-technicien', label: 'Scorecard technicien', k: 'nav.scorecard_technicien', icon: I.reporting, roles: ['responsable','admin'] },
      // XPLT10 — kiosque TV plein écran des dashboards partagés.
      { to: '/dashboards-tv',        label: 'Dashboards TV',    k: 'nav.dashboards_tv', icon: I.dashboards_tv, roles: ['responsable','admin'] },
      // XPLT10 — gestion des liens de partage (créer/révoquer).
      { to: '/reporting/dashboards/partage', label: 'Partage de dashboards', k: 'nav.dashboards_partage', icon: I.reporting, roles: ['responsable','admin'] },
    ],
  },
  {
    label: 'ADMINISTRATION', labelKey: 'nav.section.administration',
    accent: 'nuit',
    items: [
      { to: '/admin/users',          label: 'Utilisateurs',     k: 'nav.utilisateurs', icon: I.utilisateurs, roles: ['responsable','admin'] },
      { to: '/admin/roles',          label: 'Rôles',            k: 'nav.roles',      icon: I.roles_icon,    roles: ['responsable','admin'] },
      // Journal d'activité — visible UNIQUEMENT avec la permission dédiée
      // (Directeur par défaut), indépendamment du palier de menu.
      { to: '/journal',              label: "Journal d'activité", k: 'nav.journal',  icon: I.journal,    roles: ['normal','responsable','admin'], perm: 'journal_activite_voir' },
      { to: '/parametres',           label: 'Paramètres',       k: 'nav.parametres', icon: I.parametres,    roles: ['responsable','admin'] },
      // N97 — export configurable & sauvegarde : réservé à l'administrateur
      // (l'endpoint backend exige le rôle admin).
      { to: '/parametres/export',    label: 'Export / Sauvegarde', k: 'nav.export_sauvegarde', icon: I.export, roles: ['admin'] },
      // XPLT6 — CRUD des alertes de seuil sur KPI agrégés.
      { to: '/parametres/alertes-kpi', label: 'Alertes KPI',    k: 'nav.alertes_kpi', icon: I.alertes_kpi, roles: ['responsable','admin'] },
    ],
  },
]

// VX189(b) — UX1 — Les modules « coquille » s'insèrent JUSTE AVANT
// « Administration » (qui reste la dernière section). `NAV_SECTIONS` (ci-
// dessus) et `moduleNavSections` (import, lui-même figé au chargement du
// module — `import.meta.glob(..., { eager: true })`) sont TOUS DEUX
// statiques : cette fusion ne dépend d'aucun props/state et n'a donc besoin
// d'AUCUNE mémoïsation React — la calculer une seule fois au chargement du
// module (au lieu de la refaire à CHAQUE rendu de Sidebar) est strictement
// équivalent et moins cher. Seul le FILTRAGE par modules désactivés (ci-
// dessous, `useMemo`) est réellement réactif (dépend de `modulesOff`, un
// sélecteur Redux qui peut changer).
const ALL_NAV_SECTIONS = (() => {
  const adminIdx = NAV_SECTIONS.findIndex((s) => s.label === 'ADMINISTRATION')
  return adminIdx < 0
    ? [...NAV_SECTIONS, ...moduleNavSections]
    : [
        ...NAV_SECTIONS.slice(0, adminIdx),
        ...moduleNavSections,
        ...NAV_SECTIONS.slice(adminIdx),
      ]
})()

export default function Sidebar({ collapsed, onToggle, onNavigate }) {
  const dispatch    = useDispatch()
  const navigate    = useNavigate()
  const role        = useSelector((s) => s.auth.role) || 'normal'
  const permissions = useSelector((s) => s.auth.permissions) || []
  // ODX6 — clés de modules désactivés pour la société ([] par défaut).
  const modulesOff  = useSelector(selectModulesDesactives)
  const companyName = useSelector((s) => s.parametres.profile?.nom) || 'TAQINOR ERP'
  const roleMeta    = ROLE_META[role] ?? ROLE_META.normal
  const t           = useT()
  // VX86 — badge numérique sur l'item « Approbations » : masqué à 0/erreur/
  // chargement (jamais un « 0 » affiché avant que le compteur réel arrive).
  const { total: approbationsTotal, loading: approbationsLoading, error: approbationsError } = useApprobationsCount()
  const showApprobationsBadge = !approbationsLoading && !approbationsError && approbationsTotal > 0
  // VX247(c) — la progression de prise en main n'existait QUE dans l'onglet
  // Paramètres : badge « x/y » discret sur l'item Sidebar tant que <100 %.
  // Réutilise le hook PARTAGÉ (VX36) — jamais une 2e dérivation de l'état.
  const { doneCount: onboardingDone, total: onboardingTotal, allDone: onboardingAllDone } = useOnboardingSteps()

  // N93 — traduit un libellé de la coquille via sa clé i18n, en gardant le
  // libellé FR en dur comme repli (modules « coquille » sans clé → FR inchangé).
  const tr = (key, fallback) => (key ? t(key) : fallback)

  // VX189(b) — ODX6 — masque les sections des modules désactivés (liste vide
  // ⇒ no-op). `ALL_NAV_SECTIONS` (statique, module scope) recalculait cette
  // fusion à CHAQUE rendu de Sidebar avant ce fix ; seul le filtrage reste
  // réactif (dépend de `modulesOff`).
  const sections = useMemo(
    () => filterNavSections(ALL_NAV_SECTIONS, modulesOff),
    [modulesOff],
  )

  const handleLogout = async () => {
    await dispatch(logoutUser())
    navigate('/login')
  }

  return (
    <aside className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}`}>

      {/* ── Brand header (marque) ──────────────── */}
      <div className="sidebar-header">
        <div className="sidebar-brand" title={collapsed ? companyName : undefined}>
          <div className="sidebar-bolt">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="#0d1b3e">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
          </div>
          {!collapsed && (
            <span className="sidebar-brand-text">
              <span className="sidebar-company-name">{companyName}</span>
              <span className="sidebar-brand-sub">ERP Solaire</span>
            </span>
          )}
        </div>
        <button
          type="button"
          className="sidebar-toggle"
          onClick={onToggle}
          aria-label={collapsed ? 'Développer le menu' : 'Réduire le menu'}
          title={collapsed ? 'Développer' : 'Réduire'}
        >
          {collapsed ? I.chevR : I.chevL}
        </button>
      </div>

      {/* ── Role badge ─────────────────────────── */}
      {!collapsed && (
        <div className="sidebar-role">
          <span className="sidebar-role-icon">{roleMeta.icon}</span>
          <span className="sidebar-role-label">{roleMeta.label}</span>
        </div>
      )}

      {/* ── Apps épinglées (VX10) ──────────────── */}
      <Suspense fallback={null}>
        <PinnedApps collapsed={collapsed} />
      </Suspense>

      {/* ── Navigation ─────────────────────────── */}
      <nav className="sidebar-nav">
        {sections.map((section, si) => {
          const items = section.items.filter(it =>
            it.roles.includes(role) && (!it.perm || permissions.includes(it.perm)))
          if (items.length === 0) return null
          // VX8 — accent de module posé en variable CSS sur la section ; les
          // sections « coquille » (moduleNavSections) portent déjà `nav.accent`
          // au même format, `undefined`/`null` reste neutre (repli existant).
          const accentStyle = section.accent
            ? { '--module-accent': `var(--module-accent-${section.accent})` }
            : undefined
          return (
            <div key={si} className="sidebar-section" style={accentStyle}>
              {section.label && !collapsed && (
                <div className="sidebar-section-label">{tr(section.labelKey, section.label)}</div>
              )}
              {items.map(item => {
                const label = tr(item.k, item.label)
                return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end
                  // FG16 — ancres du guide d'accueil (coachmarks) sur quelques
                  // liens clés : le spotlight cible ces attributs `data-coach`.
                  data-coach={COACH_ANCHORS[item.to]}
                  // VX175(d) — `title` était réservé à l'état REPLIÉ ; en état
                  // DÉPLIÉ, un libellé tronqué par `text-overflow: ellipsis`
                  // (index.css) à texte-zoom élevé n'avait aucun repère
                  // (tooltip natif) pour lire le nom complet.
                  title={label}
                  onClick={onNavigate}
                  // VX58 — précharge le chunk de la destination dès le survol
                  // souris/clavier, avant le clic réel.
                  onMouseEnter={() => prefetchRoute(item.to)}
                  onFocus={() => prefetchRoute(item.to)}
                  // I135 — l'item actif porte aria-current="page" : NavLink le
                  // pose automatiquement sur le lien actif (valeur par défaut
                  // "page"), en plus de la classe `active` (pastille discrète).
                  className={({ isActive }) => `sidebar-nav-item${isActive ? ' active' : ''}`}
                >
                  <span className="sidebar-nav-icon">{item.icon}</span>
                  {!collapsed && <span className="sidebar-nav-label">{label}</span>}
                  {/* VX86 — pastille de compte sur « Approbations » (nav + tiroir replié). */}
                  {item.to === '/approbations' && showApprobationsBadge && (
                    <span
                      className="sidebar-nav-badge"
                      aria-label={`${approbationsTotal} approbation${approbationsTotal > 1 ? 's' : ''} en attente`}
                    >
                      {approbationsTotal > 99 ? '99+' : approbationsTotal}
                    </span>
                  )}
                  {/* VX247(c) — badge de progression « x/y » sur Paramètres tant
                      que la prise en main n'est pas terminée à 100 %. */}
                  {item.to === '/parametres' && !onboardingAllDone && (
                    <span
                      className="sidebar-nav-badge"
                      aria-label={`Prise en main : ${onboardingDone} sur ${onboardingTotal} étapes complétées`}
                    >
                      {onboardingDone}/{onboardingTotal}
                    </span>
                  )}
                </NavLink>
                )
              })}
            </div>
          )
        })}
      </nav>

      {/* ── Pastille d'impact du parc (VX157) ──── */}
      <Suspense fallback={null}>
        <ImpactPastille collapsed={collapsed} />
      </Suspense>

      {/* ── Logout ─────────────────────────────── */}
      <button
        className="sidebar-logout"
        onClick={handleLogout}
        title={collapsed ? 'Déconnexion' : undefined}
      >
        {I.logout}
        {!collapsed && <span className="sidebar-logout-label">Déconnexion</span>}
      </button>
    </aside>
  )
}
