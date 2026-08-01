// ODY4 — L'APP ACTIVE : dans une app, la coquille est CELLE de l'app.
// ----------------------------------------------------------------------------
// Le cœur du paradigme « ERP-Apps » (fondateur 2026-08-01) : on n'entre pas
// dans un écran, on entre dans une APP. Ce module dérive l'app active de la
// ROUTE COURANTE — jamais d'un état de coquille mémorisé — pour que trois
// propriétés soient vraies par CONSTRUCTION :
//
//   1. un deep-link / F5 / retour navigateur rend exactement la même coquille
//      qu'un clic (aucun état à resynchroniser, donc aucun écran « orphelin
//      de coquille ») ;
//   2. suivre un lien inter-apps (lead → devis, ticket → équipement…) bascule
//      la coquille sur l'app CIBLE tout seul — c'est l'acquis ODY7, obtenu
//      sans instrumenter chaque point d'appel ;
//   3. il n'existe AUCUN deuxième registre d'apps : l'identité de l'app active
//      (label, accent VX8, icône, cockpit) est lue dans `useInstalledApps()`
//      (ODY1 — registre ODX ∩ modules actifs société ODX6 ∩ rôle/permission
//      ARC47), ce fichier n'ajoutant QUE la résolution route → clé d'app.
//
// Pas de React Context ni de Provider à monter : l'app active est une fonction
// PURE de `location.pathname`, donc un hook suffit (aucun ordre de montage à
// respecter, aucun test à envelopper dans un provider de plus). Le nom de
// fichier reste celui du plan ; l'ajout ultérieur d'un Provider (annonce
// aria-live ODY32, mémoire de reprise ODY29) sera purement additif.
import { useCallback, useEffect, useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { CalendarClock } from 'lucide-react'
import { moduleConfigs } from '../../router/moduleRoutes'
import useInstalledApps from './useInstalledApps'
// ODY29 — mémoire de reprise par app+utilisateur (sessionStorage, source
// UNIQUE dans `appPrefs.js` : ce fichier écrit, le Menu d'accueil lit).
import { writeResume } from './appPrefs'
// ODY30 — kill-switch build-time de la bascule de coquille (défaut ON). Sa
// DÉFINITION vit dans un module sans import (`appsShellFlag.js`) parce que ses
// deux lecteurs — ce fichier et `Layout.jsx` — sont liés par la chaîne
// Layout → Sidebar → ActiveAppContext : le définir ici ou là créerait un cycle.
import { APPS_SHELL_ENABLED } from './appsShellFlag'

export { APPS_SHELL_ENABLED }

// Menu d'accueil plein écran (ODY2, lane parallèle) — LA sortie canonique de
// l'immersion. Constante partagée pour que Sidebar/Header pointent au même
// endroit sans jamais re-coder le chemin en dur.
export const HOME_MENU_PATH = '/apps'

const EMPTY_PERMISSIONS = []

// Poids d'ORIGINE d'une déclaration de chemin dans un `module.config.jsx`.
// À longueur de préfixe ÉGALE, la déclaration la plus « intentionnelle »
// gagne : un item de NAV (l'app affiche ce lien dans SON menu) l'emporte sur
// une simple route (l'app héberge l'écran), qui l'emporte sur un titre, qui
// l'emporte sur un libellé de section. Cas réel que cette règle tranche :
// `/admin/users` est une `route` de `features/admin/module.config.jsx` mais un
// item de `nav` de `features/parametres/module.config.jsx` (ODY23 : les écrans
// d'administration appartiennent à l'app Paramètres) → l'app active y est
// « Paramètres », comme le menu le promet à l'utilisateur.
const SOURCE_WEIGHT = { nav: 3, route: 2, title: 1, section: 0 }

// `/crm/leads?new=1` → `/crm/leads` ; `/crm/leads/:id` → `/crm/leads`.
function normalizeDeclaredPath(path) {
  if (typeof path !== 'string' || !path.startsWith('/')) return null
  const withoutQuery = path.split('?')[0].split('#')[0]
  const segments = []
  for (const seg of withoutQuery.split('/')) {
    if (seg.startsWith(':') || seg === '*') break
    segments.push(seg)
  }
  const joined = segments.join('/')
  const trimmed = joined.replace(/\/+$/, '')
  return trimmed.startsWith('/') && trimmed.length > 1 ? trimmed : null
}

/**
 * buildAppRouteIndex — index PUR « préfixe de route → clé d'app », construit à
 * partir du registre des `module.config.jsx` (aucune table de correspondance
 * écrite à la main : ajouter une app = déposer son fichier, comme UX1).
 * Trié du préfixe le PLUS LONG au plus court : `/ventes/devis/nouveau` gagne
 * sur `/ventes`.
 */
export function buildAppRouteIndex(configs) {
  const best = new Map()
  ;(configs ?? []).forEach((cfg, order) => {
    if (!cfg?.key) return
    const claim = (rawPath, source) => {
      const prefix = normalizeDeclaredPath(rawPath)
      if (!prefix) return
      const weight = SOURCE_WEIGHT[source]
      const current = best.get(prefix)
      if (!current || weight > current.weight) {
        best.set(prefix, { key: cfg.key, weight, order })
      }
    }
    ;(cfg.nav?.items ?? []).forEach((item) => claim(item?.to, 'nav'))
    ;(cfg.routes ?? []).forEach((route) => claim(route?.path, 'route'))
    ;(cfg.titles ?? []).forEach((entry) => claim(entry?.[0], 'title'))
    Object.keys(cfg.sectionLabels ?? {}).forEach((seg) => claim(`/${seg}`, 'section'))
  })
  return Array.from(best.entries())
    .map(([prefix, meta]) => ({ prefix, ...meta }))
    .sort((a, b) => b.prefix.length - a.prefix.length || a.order - b.order)
}

/**
 * resolveAppKey — clé de l'app qui possède `pathname`, ou `null` si le chemin
 * n'appartient à aucune app (Menu d'accueil, préférences, écrans transverses)
 * → coquille NEUTRE. Comparaison par SEGMENT (jamais `startsWith` brut :
 * `/crm` ne doit pas capturer `/crmXYZ`).
 */
export function resolveAppKey(index, pathname) {
  const path = String(pathname || '/').split('?')[0].split('#')[0].replace(/\/+$/, '') || '/'
  for (const entry of index ?? []) {
    if (path === entry.prefix || path.startsWith(`${entry.prefix}/`)) return entry.key
  }
  return null
}

// Index figé au chargement du module : `moduleConfigs` est lui-même statique
// (`import.meta.glob(..., { eager: true })`), le calculer une seule fois est
// strictement équivalent et gratuit.
const ROUTE_INDEX = buildAppRouteIndex(moduleConfigs)

/* ODY4 — items dont la ROUTE appartient déjà à une app (elle est déclarée dans
   le `routes` de son `module.config.jsx`) mais dont l'ENTRÉE DE MENU vivait
   encore dans le littéral codé en dur de `Sidebar.jsx`. Ils sont rattachés ici
   à leur app pour ne perdre AUCUNE destination en retirant ce littéral. Table
   volontairement minuscule et destinée à disparaître : quand la lane
   propriétaire des `module.config.jsx` déclarera ces items dans le `nav` de
   leur app, l'entrée correspondante se supprime ici sans autre changement.
   Source UNIQUE : la Sidebar legacy ET le mode immersion lisent cette table. */
export const ORPHAN_NAV_ITEMS = {
  // VX83 — « Ma file » : la file de travail unique, route `/activites`
  // déclarée dans `features/crm/module.config.jsx` (`routes`), sans item de
  // nav correspondant.
  crm: [
    {
      to: '/activites',
      label: 'Ma file',
      k: 'nav.activites',
      icon: <CalendarClock size={17} strokeWidth={1.75} aria-hidden="true" />,
      roles: ['normal', 'responsable', 'admin'],
    },
  ],
}

// Même règle de visibilité qu'ailleurs dans la coquille (palier + permission
// ERP fine optionnelle) — cf. `useInstalledApps.js`, `Sidebar.jsx`.
function isItemVisible(item, role, permissions) {
  return !!item?.roles?.includes(role) && (!item.perm || permissions.includes(item.perm))
}

/**
 * appNavItems — items de menu d'une app, dans l'ordre de son `module.config`,
 * filtrés par rôle/permission. PURE (testable sans React).
 */
export function appNavItems(config, role, permissions = EMPTY_PERMISSIONS) {
  if (!config) return []
  const declared = config.nav?.items ?? []
  const orphans = ORPHAN_NAV_ITEMS[config.key] ?? []
  return [...declared, ...orphans].filter((it) => isItemVisible(it, role, permissions))
}

/* ODY29 — `useActiveApp` a plusieurs consommateurs montés en même temps
   (Sidebar, Header, BottomTabBar) : sans garde, chaque navigation écrirait la
   même route trois fois. Cette empreinte de module rend l'écriture EXACTEMENT
   une par navigation. Elle ne porte aucun état fonctionnel — la vérité reste
   le sessionStorage. */
let derniereEmpreinteReprise = ''

/**
 * useActiveApp — l'app active déduite de la route, ou `null` (coquille neutre)
 * hors de toute app, quand l'app n'est pas installée/autorisée, ou quand le
 * kill-switch ODY30 est OFF (chemin de secours legacy).
 *
 * Effet de bord (ODY29) : mémorise la route courante comme point de reprise de
 * l'app active. C'est ici, et nulle part ailleurs, parce que c'est le seul
 * endroit qui connaît DÉJÀ le couple (route → app) sans le recalculer.
 *
 * @returns {null | {key, label, icon, accent, to, description, items}}
 */
export function useActiveApp() {
  const { pathname } = useLocation()
  // ODY1 — SOURCE UNIQUE de « mes apps » : jamais une 2e liste ici.
  const apps = useInstalledApps()
  const role = useSelector((s) => s.auth.role) || 'normal'
  const permissions = useSelector((s) => s.auth.permissions) || EMPTY_PERMISSIONS
  // ODY29 — la mémoire de reprise est propre à l'utilisateur : deux comptes qui
  // se succèdent sur le même poste ne reprennent jamais la session de l'autre.
  const userId = useSelector((s) => s.auth.user?.id)

  const app = useMemo(() => {
    if (!APPS_SHELL_ENABLED) return null
    const key = resolveAppKey(ROUTE_INDEX, pathname)
    if (!key) return null
    const trouvee = apps.find((a) => a.key === key)
    // App désactivée pour la société, ou aucun écran autorisé pour ce rôle :
    // on ne fabrique PAS une identité d'app à partir du registre brut (ce
    // serait la 2e source d'apps interdite) — coquille neutre.
    if (!trouvee) return null
    const config = moduleConfigs.find((c) => c.key === key)
    return { ...trouvee, items: appNavItems(config, role, permissions) }
  }, [pathname, apps, role, permissions])

  const appKey = app?.key
  useEffect(() => {
    if (!appKey) return
    const empreinte = `${userId ?? ''}|${appKey}|${pathname}`
    if (empreinte === derniereEmpreinteReprise) return
    derniereEmpreinteReprise = empreinte
    writeResume(appKey, userId, pathname)
  }, [appKey, userId, pathname])

  return app
}

/**
 * useAppVisibility — ODY27 : LE prédicat « cette app / ce chemin est-il visible
 * pour cette société et ce rôle ? », pour les surfaces TRANSVERSES qui échappent
 * à l'immersion (palette ⌘K, recherche globale, cloche de notifications,
 * Dashboard). Adossé à `useInstalledApps()` (ODY1) : ces surfaces n'ont AUCUNE
 * liste d'apps locale, elles posent une question à la source unique.
 *
 * `isPathVisible` répond VRAI pour un chemin qui n'appartient à aucune app
 * (Menu d'accueil, préférences, écrans transverses) : le filtre ne masque QUE
 * ce qui appartient à une app absente — jamais par défaut.
 */
export function useAppVisibility() {
  const apps = useInstalledApps()
  const visibleKeys = useMemo(() => new Set(apps.map((a) => a.key)), [apps])
  return useMemo(() => ({
    isAppVisible: (key) => !key || visibleKeys.has(key),
    isPathVisible: (to) => {
      if (!to) return true
      const key = resolveAppKey(ROUTE_INDEX, String(to).split('?')[0].split('#')[0])
      return !key || visibleKeys.has(key)
    },
  }), [visibleKeys])
}

/**
 * crossAppTransition — description PURE d'une navigation : app de départ, app
 * d'arrivée, et si la coquille doit basculer. Utilisée par les tests ODY7 et
 * par `useCrossAppNavigate` ci-dessous.
 */
export function crossAppTransition(fromPath, toPath) {
  const from = resolveAppKey(ROUTE_INDEX, fromPath)
  const to = resolveAppKey(ROUTE_INDEX, toPath)
  return { from, to, switched: !!to && to !== from }
}

/**
 * useCrossAppNavigate — ODY7 : LE point d'entrée des navigations inter-apps
 * (lead → devis, devis → facture/BC/chantier, ticket → équipement/client,
 * produit → devis…). La coquille étant dérivée de la route, une navigation
 * normale suffit à basculer d'app — cette fonction ne « répare » donc rien à
 * l'exécution : elle rend la bascule NOMMÉE et TESTABLE, et garantit qu'aucun
 * appelant ne conserve d'état de coquille de l'app source (il n'y en a pas).
 * Renvoie la transition (`{from, to, switched}`) pour les tests/l'annonce.
 */
export function useCrossAppNavigate() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  return useCallback((to, options) => {
    const transition = crossAppTransition(pathname, typeof to === 'string' ? to : pathname)
    navigate(to, options)
    return transition
  }, [navigate, pathname])
}

export default useActiveApp
