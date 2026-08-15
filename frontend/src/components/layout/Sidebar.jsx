import { lazy, Suspense, useMemo } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  LogOut, ChevronLeft, ChevronRight, Key, Briefcase, User as UserIcon, LayoutGrid,
} from 'lucide-react'
import { logoutUser } from '../../features/auth/store/authSlice'
// UX1 — Sections de navigation des modules « coquille », enregistrées par
// chaque module via `features/<module>/module.config.jsx` (aucun couplage ici).
// ODX7 — `moduleConfigs` sert aussi à lire par clé les sections legacy
// (stock/crm/ventes/installations/sav/reporting), déplacées de ce fichier vers
// leur propre `module.config.jsx` (cf. `navFor` ci-dessous).
import { moduleNavSections, moduleConfigs } from '../../router/moduleRoutes'
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
// WIR171 — règle d'autorisation PARTAGÉE avec le roleLoader (miroir serveur) :
// aucune copie de « palier ET permission » ici.
import { itemAutorise } from '../../router/navPermission'
// ODY4 — l'app active dérivée de la route + le kill-switch de bascule (ODY30).
import {
  useActiveApp, APPS_SHELL_ENABLED, HOME_MENU_PATH, ORPHAN_NAV_ITEMS,
} from '../../lib/apps/ActiveAppContext'
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
// Toutes les icônes de la coquille viennent d'une seule librairie, à une
// épaisseur (1.75) et des tailles standardisées issues de l'échelle 3.5/4/5
// (14 / 16 / 20 px). `aria-hidden` car le libellé textuel porte déjà
// l'accessibilité.
// ODY4 — la table `I` ne porte plus que les icônes de la COQUILLE elle-même
// (chevrons, déconnexion, badges de rôle, sortie ⊞) : les icônes des
// DESTINATIONS vivent désormais toutes dans le `module.config.jsx` de leur app,
// puisque plus aucune section de nav n'est codée en dur ici.
const ICON_MD = 17     // ~4 (16–18 px) — items de navigation
const ICON_SM = 13     // ~3.5 (14 px)  — badges de rôle (denses)
const STROKE = 1.75
const mk = (Comp, size = ICON_MD) => (
  <Comp size={size} strokeWidth={STROKE} aria-hidden="true" />
)

const I = {
  logout:       mk(LogOut),
  chevL:        mk(ChevronLeft),
  chevR:        mk(ChevronRight),
  key:          mk(Key, ICON_SM),
  briefcase:    mk(Briefcase, ICON_SM),
  user_single:  mk(UserIcon, ICON_SM),
  apps:         mk(LayoutGrid),
}

// Référence STABLE (jamais un `[]` littéral recréé à chaque rendu, qui
// invaliderait les `useMemo` en aval — même patron que BottomTabBar.jsx).
const EMPTY_PERMISSIONS = []

const ROLE_META = {
  admin:       { label: 'Administrateur', icon: I.key },
  responsable: { label: 'Responsable',    icon: I.briefcase },
  normal:      { label: 'Utilisateur',    icon: I.user_single },
}

// ODX7 — les sections legacy STOCK/CRM/VENTES/CHANTIERS/APRÈS-VENTE/ANALYSE ne
// sont pas des littéraux ici : elles vivent dans le `module.config.jsx` de leur
// app. `navFor(key)` va lire cette section par clé, à LA MÊME PLACE dans l'ordre
// d'affichage qu'avant.
const navFor = (key) => {
  const cfg = moduleConfigs.find((c) => c.key === key)
  return cfg && cfg.nav ? { key: cfg.key, ...cfg.nav } : null
}

// eslint-disable-next-line react-refresh/only-export-components
export const NAV_SECTIONS = [
  // ODY4 — Les quatre derniers blocs codés EN DUR ici (tête Dashboard/Ma file/
  // Messages, DOCUMENTS, INTELLIGENCE, ADMINISTRATION) ont été RETIRÉS : leurs
  // destinations sont désormais déclarées par le `module.config.jsx` de leur
  // app (`admin` → Tableau de bord, `chat` → Messages, `ged` → Documents,
  // `ia` → Intelligence, `parametres` → Administration/Paramètres,
  // `reporting` → Journal d'activité). Tant que ces littéraux coexistaient
  // avec les nouvelles configs, la coquille rendait certaines sections DEUX
  // FOIS (deux « DOCUMENTS », INTELLIGENCE/ADMINISTRATION dupliquées, deux
  // liens `/messages`) — c'est ce doublon que leur retrait résorbe.
  // Seul reliquat : « Ma file » (VX83), dont la route `/activites` appartient
  // bien à l'app CRM mais qui n'a pas encore d'item dans le `nav` de son
  // module.config — rattaché à CRM par `ORPHAN_NAV_ITEMS` (source unique,
  // partagée avec le mode immersion), et gaté par la MÊME clé de module.
  { key: 'crm', label: null, accent: null, items: ORPHAN_NAV_ITEMS.crm },
  // ODX6 — la clé de module (posée par chaque module.config.jsx) gate le
  // nav/route (masqué si désactivé pour la société). Absence de toggle ⇒
  // affiché comme aujourd'hui.
  navFor('stock'),
  navFor('crm'),
  navFor('ventes'),
  navFor('installations'),
  navFor('sav'),
  navFor('reporting'),
// ODX7 — `navFor()` peut renvoyer `null` si un module.config.jsx venait à
// perdre sa section `nav` (défensif, ne devrait jamais arriver en usage
// normal) : `.filter(Boolean)` neutralise ce cas sans jamais rendre un `null`.
].filter(Boolean)

// VX189(b) — UX1 — Les modules « coquille » s'insèrent JUSTE APRÈS les six
// sections legacy ci-dessus. `NAV_SECTIONS` et `moduleNavSections` (import,
// lui-même figé au chargement du module — `import.meta.glob(..., { eager:
// true })`) sont TOUS DEUX statiques : cette fusion ne dépend d'aucun
// props/state et n'a donc besoin d'AUCUNE mémoïsation React. Seul le FILTRAGE
// par modules désactivés (plus bas, `useMemo`) est réellement réactif.
// ODX7 — les 6 clés legacy sont lues explicitement par `navFor()` dans
// `NAV_SECTIONS` : leur `nav` apparaît AUSSI dans `moduleNavSections` (le
// registre générique, qui collecte `.nav` sur TOUTES les configs). Sans ce
// filtre, ces 6 sections seraient rendues deux fois.
// Exportée : BottomTabBar.jsx (VX12, tiroir mobile « Plus ») reconstruit le
// même merge NAV_SECTIONS + moduleNavSections et a besoin du même filtre pour
// éviter la même duplication côté mobile.
// eslint-disable-next-line react-refresh/only-export-components
export const LEGACY_NAV_KEYS = new Set(['stock', 'crm', 'ventes', 'installations', 'sav', 'reporting'])
const coquilleNavSections = moduleNavSections.filter((s) => !LEGACY_NAV_KEYS.has(s.key))

const ALL_NAV_SECTIONS = [...NAV_SECTIONS, ...coquilleNavSections]

export default function Sidebar({ collapsed, onToggle, onNavigate }) {
  const dispatch    = useDispatch()
  const navigate    = useNavigate()
  const role        = useSelector((s) => s.auth.role) || 'normal'
  const permissions = useSelector((s) => s.auth.permissions) || EMPTY_PERMISSIONS
  // WIR171 — nom du rôle FIN (null pour un compte hérité) : c'est lui qui
  // distingue « la permission décide » de « repli palier » (cf. navPermission).
  const roleNom    = useSelector((s) => s.auth.role_nom) || null
  // ODX6 — clés de modules désactivés pour la société ([] par défaut).
  const modulesOff  = useSelector(selectModulesDesactives)
  const companyName = useSelector((s) => s.parametres.profile?.nom) || 'TAQINOR ERP'
  const roleMeta    = ROLE_META[role] ?? ROLE_META.normal
  const t           = useT()
  // ODY4 — l'app active (null hors app ⇒ coquille neutre, ou flag ODY30 OFF).
  const activeApp   = useActiveApp()
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
  // ⇒ no-op). Chemin LEGACY uniquement (flag ODY30 OFF) : en mode Apps, la nav
  // est celle de l'app active.
  const legacySections = useMemo(
    () => filterNavSections(ALL_NAV_SECTIONS, modulesOff),
    [modulesOff],
  )

  const handleLogout = async () => {
    await dispatch(logoutUser())
    navigate('/login')
  }

  const badges = {
    showApprobationsBadge, approbationsTotal,
    onboardingAllDone, onboardingDone, onboardingTotal,
  }

  // ── Chemin LEGACY (ODY30 OFF) — pile de navigation GLOBALE ────────────────
  // SMOKE D'URGENCE uniquement : rendu strictement identique à celui d'avant la
  // bascule ODY4, à ceci près que plus aucune section n'y est codée en dur
  // (donc plus de doublon). Non couvert par les tests unitaires (assumé et
  // documenté par ODY30) ; son retrait est queued en ODY33.
  if (!APPS_SHELL_ENABLED) {
    return (
      <aside className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}`}>
        <SidebarBrand collapsed={collapsed} companyName={companyName} onToggle={onToggle} />
        {!collapsed && <SidebarRoleBadge roleMeta={roleMeta} />}
        <Suspense fallback={null}>
          <PinnedApps collapsed={collapsed} />
        </Suspense>
        <nav className="sidebar-nav">
          {legacySections.map((section, si) => {
            const items = section.items.filter(
              (it) => itemAutorise(it, { tier: role, roleNom, permissions }))
            if (items.length === 0) return null
            const accentStyle = section.accent
              ? { '--module-accent': `var(--module-accent-${section.accent})` }
              : undefined
            return (
              <div key={si} className="sidebar-section" style={accentStyle}>
                {section.label && !collapsed && (
                  <div className="sidebar-section-label">{tr(section.labelKey, section.label)}</div>
                )}
                <SidebarNavItems
                  items={items} collapsed={collapsed} onNavigate={onNavigate}
                  tr={tr} badges={badges}
                />
              </div>
            )
          })}
        </nav>
        <Suspense fallback={null}>
          <ImpactPastille collapsed={collapsed} />
        </Suspense>
        <SidebarLogout collapsed={collapsed} onLogout={handleLogout} />
      </aside>
    )
  }

  // ── Mode APPS (défaut) — la coquille EST celle de l'app active ────────────
  // ODY4 : en immersion, la sidebar ne rend QUE les items de l'app courante.
  // Aucune destination d'une AUTRE app n'existe dans ce DOM — ni pile globale,
  // ni bande d'apps épinglées : la seule affordance inter-apps est le pied
  // « ⊞ Toutes les apps » (et, par-dessus, les raccourcis power-user).
  const accentStyle = activeApp?.accent
    ? { '--module-accent': `var(--module-accent-${activeApp.accent})` }
    : undefined

  return (
    <aside
      className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}${activeApp ? ' sidebar--app' : ' sidebar--neutral'}`}
      data-app={activeApp ? activeApp.key : undefined}
      style={accentStyle}
    >
      <SidebarBrand collapsed={collapsed} companyName={companyName} onToggle={onToggle} />

      {/* ── Identité de l'app active (icône + nom + accent VX8) ───────────
          Cliquable → cockpit de l'app (1er écran autorisé, ODY1). */}
      {activeApp && (
        <Link
          to={activeApp.to}
          className="sidebar-app"
          onClick={onNavigate}
          title={activeApp.label}
          aria-label={`Application ${activeApp.label} — aller à son écran d'accueil`}
        >
          <span className="sidebar-app-icon" aria-hidden="true">{activeApp.icon}</span>
          {!collapsed && <span className="sidebar-app-name">{activeApp.label}</span>}
        </Link>
      )}

      {!collapsed && <SidebarRoleBadge roleMeta={roleMeta} />}

      {/* ── Navigation de l'app (et d'ELLE SEULE) ────────────────────────── */}
      <nav className="sidebar-nav" aria-label={activeApp ? `Navigation ${activeApp.label}` : 'Navigation'}>
        {activeApp ? (
          <div className="sidebar-section" style={accentStyle}>
            <SidebarNavItems
              items={activeApp.items} collapsed={collapsed} onNavigate={onNavigate}
              tr={tr} badges={badges}
            />
          </div>
        ) : (
          // Coquille NEUTRE minimale : Menu d'accueil, préférences, écrans
          // transverses. Aucune app n'est « ouverte », donc aucune nav d'app.
          !collapsed && (
            <p className="sidebar-neutral-hint">
              Choisissez une application pour commencer.
            </p>
          )
        )}
      </nav>

      <Suspense fallback={null}>
        <ImpactPastille collapsed={collapsed} />
      </Suspense>

      {/* ── Sortie : retour au Menu d'accueil (⊞) ─────────────────────────
          ODY5 fait du bouton ⊞ du HEADER la sortie canonique testée ; celui-ci
          est son jumeau au pied de la nav, pour la souris comme pour le
          clavier (même destination, jamais un 2e comportement). */}
      <Link
        to={HOME_MENU_PATH}
        className="sidebar-apps-exit"
        onClick={onNavigate}
        aria-label="Toutes les apps"
        title="Toutes les apps"
      >
        <span className="sidebar-apps-exit-icon" aria-hidden="true">{I.apps}</span>
        {!collapsed && <span className="sidebar-apps-exit-label">Toutes les apps</span>}
      </Link>

      <SidebarLogout collapsed={collapsed} onLogout={handleLogout} />
    </aside>
  )
}

function SidebarBrand({ collapsed, companyName, onToggle }) {
  return (
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
  )
}

function SidebarRoleBadge({ roleMeta }) {
  return (
    <div className="sidebar-role">
      <span className="sidebar-role-icon">{roleMeta.icon}</span>
      <span className="sidebar-role-label">{roleMeta.label}</span>
    </div>
  )
}

function SidebarLogout({ collapsed, onLogout }) {
  return (
    <button
      className="sidebar-logout"
      onClick={onLogout}
      title={collapsed ? 'Déconnexion' : undefined}
    >
      {I.logout}
      {!collapsed && <span className="sidebar-logout-label">Déconnexion</span>}
    </button>
  )
}

// Rendu d'une liste d'items de nav — mutualisé entre le mode Apps (items de
// l'app active) et le chemin legacy (sections globales) : un SEUL rendu de
// lien, donc aucune divergence de comportement (prefetch VX58, ancres
// coachmarks FG16, aria-current I135, badges VX86/VX247) entre les deux modes.
function SidebarNavItems({ items, collapsed, onNavigate, tr, badges }) {
  return items.map((item) => {
    const label = tr(item.k, item.label)
    return (
      <NavLink
        key={item.to}
        to={item.to}
        end
        // FG16 — ancres du guide d'accueil (coachmarks) sur quelques liens
        // clés : le spotlight cible ces attributs `data-coach`.
        data-coach={COACH_ANCHORS[item.to]}
        // VX175(d) — `title` était réservé à l'état REPLIÉ ; en état DÉPLIÉ, un
        // libellé tronqué par `text-overflow: ellipsis` (index.css) à
        // texte-zoom élevé n'avait aucun repère (tooltip natif).
        title={label}
        onClick={onNavigate}
        // VX58 — précharge le chunk de la destination dès le survol
        // souris/clavier, avant le clic réel.
        onMouseEnter={() => prefetchRoute(item.to)}
        onFocus={() => prefetchRoute(item.to)}
        // I135 — l'item actif porte aria-current="page" : NavLink le pose
        // automatiquement sur le lien actif, en plus de la classe `active`.
        className={({ isActive }) => `sidebar-nav-item${isActive ? ' active' : ''}`}
      >
        <span className="sidebar-nav-icon">{item.icon}</span>
        {!collapsed && <span className="sidebar-nav-label">{label}</span>}
        {/* VX86 — pastille de compte sur « Approbations » (nav + tiroir replié). */}
        {item.to === '/approbations' && badges.showApprobationsBadge && (
          <span
            className="sidebar-nav-badge"
            aria-label={`${badges.approbationsTotal} approbation${badges.approbationsTotal > 1 ? 's' : ''} en attente`}
          >
            {badges.approbationsTotal > 99 ? '99+' : badges.approbationsTotal}
          </span>
        )}
        {/* VX247(c) — badge de progression « x/y » sur Paramètres tant que la
            prise en main n'est pas terminée à 100 %. */}
        {item.to === '/parametres' && !badges.onboardingAllDone && (
          <span
            className="sidebar-nav-badge"
            aria-label={`Prise en main : ${badges.onboardingDone} sur ${badges.onboardingTotal} étapes complétées`}
          >
            {badges.onboardingDone}/{badges.onboardingTotal}
          </span>
        )}
      </NavLink>
    )
  })
}
