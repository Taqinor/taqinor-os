/* UX1 — Registre de modules ERP.
   ----------------------------------------------------------------------------
   Chaque module « coquille » (Comptabilité, Paie, RH, Flotte, QHSE, Contrats,
   Gestion de projet, GED, KB, Litiges…) dépose UN SEUL fichier
   `src/features/<module>/module.config.jsx` (export par défaut) et s'enregistre
   ici — SANS toucher au routeur, à la Sidebar ni à routes.meta. Résultat : les
   lanes de chaque module sont totalement disjointes (aucun fichier partagé), et
   ajouter un module = déposer un fichier.

   Forme d'une config de module (export default) :
     {
       key: 'compta',                       // identifiant stable
       order: 10,                           // ordre d'affichage (défaut 100)
       nav: {                               // section Sidebar (gatée)
         label: 'COMPTABILITÉ',
         items: [{ to, label, icon, roles:['responsable','admin'], perm? }],
       },
       titles: [['/comptabilite', 'Comptabilité']],  // routes.meta (spécifique→général)
       sectionLabels: { comptabilite: 'Comptabilité' }, // fil d'Ariane (1er segment)
       routes: [{ path:'/comptabilite', component: Lazy, roles?, perm? }],
     }

   Contrats de sécurité préservés :
   - `router/index.test.jsx` n'inspecte QUE la source de `index.jsx` : les
     `<Suspense>` et imports de pages vivent ici (ou dans les configs), jamais
     dans `index.jsx` → le contrat de code-splitting reste vert.
   - Les routes sont gatées via le MÊME `roleLoader`/`authLoader` que le reste de
     l'app (reflète le gating du menu). */

// Collecte EAGER de toutes les configs de module (données + composants lazy).
const configModules = import.meta.glob('../features/*/module.config.jsx', { eager: true })

const configs = Object.values(configModules)
  .map((m) => m.default)
  .filter(Boolean)
  // Ordre déterministe : `order` puis `key` (stable d'un build à l'autre).
  .sort(
    (a, b) =>
      (a.order ?? 100) - (b.order ?? 100) ||
      String(a.key ?? '').localeCompare(String(b.key ?? '')),
  )

// Sections de navigation Sidebar (gatées par rôle/permission, comme les autres).
// ODX6 — on propage la clé de module (`c.key`) sur la section de nav pour que le
// gating par module actif/désactivé (router/moduleGating) puisse la masquer si
// la société a désactivé ce module. Le `key` déjà présent dans un `nav` explicite
// n'est pas écrasé.
export const moduleNavSections = configs
  .filter((c) => c.nav)
  .map((c) => ({ key: c.key, ...c.nav }))

// Titres de page (routes.meta) : [préfixe, titre], du plus spécifique au général.
export const moduleTitles = configs.flatMap((c) => c.titles ?? [])

// Libellés de section (fil d'Ariane) : { premierSegment: 'Libellé' }.
export const moduleSectionLabels = Object.assign(
  {},
  ...configs.map((c) => c.sectionLabels ?? {}),
)

/* Construit les objets de route react-router à partir des configs. On réutilise
   `WithLayout` / `authLoader` / `roleLoader` fournis PAR le routeur (injection)
   pour éviter un cycle d'import et garder tout `<Suspense>` hors de `index.jsx`.
   `WithLayout` monte déjà une frontière Suspense : le composant lazy du module y
   est simplement rendu comme enfant. */
export function buildModuleRoutes(deps) {
  const { authLoader, roleLoader } = deps
  // ODX6 — garde de module : un loader qui, une fois la session/le rôle
  // vérifiés, redirige vers /dashboard si le module de cette route est
  // désactivé pour la société. `moduleLoader(key)` reçoit du routeur le loader
  // de base (auth ou rôle) et l'enveloppe. Sans `key` (route sans module) ou
  // sans `moduleLoader` fourni, le comportement est inchangé.
  const moduleLoader = deps.moduleLoader
  // Variable PascalCase (couverte par varsIgnorePattern '^[A-Z_]') plutôt qu'un
  // argument déstructuré : le lint local ne compte pas l'usage JSX seul.
  const WithLayout = deps.WithLayout
  return configs.flatMap((c) =>
    (c.routes ?? []).map((r) => {
      const Comp = r.component
      const base = r.roles ? roleLoader(r.roles, r.perm) : authLoader
      const loader = (c.key && moduleLoader) ? moduleLoader(c.key, base) : base
      return {
        path: r.path,
        loader,
        element: (
          <WithLayout>
            <Comp />
          </WithLayout>
        ),
      }
    }),
  )
}

// Exposé pour tests / introspection.
export const moduleConfigs = configs
