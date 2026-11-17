# Recherche L3 n°7/8 — Ce que le système de design de l'ERP offre déjà

Lu dans cette session (chemins relatifs à `frontend/`). Non vérifié = signalé.

## 1. Jetons
| Sujet | Fait | Preuve |
|---|---|---|
| Fichier source | un seul : `src/design/tokens.css` (1 101 l.), importé par `src/index.css:7` (+ ~44 feuilles `src/styles/**`) | index.css:1-54 |
| Couleurs | sémantiques `--background --foreground --card --popover --primary --secondary --muted --accent --destructive --success --warning --info` + `-foreground`, et `--primary-text/--success-text/--warning-text` (variantes AA pour du TEXTE) | tokens.css:44-100 |
| Marque | `--primary` = or laiton `#e8b54a` (texte foncé dessus) ; rampes OKLCH azur/brass/encre/lune | tokens.css:44-50, 60-67 |
| Accents de module | `--module-accent-{brass,azur,nuit,success,destructive,warning,lune}` ; un module en choisit un via `nav.accent` | tokens.css:~100-112 ; crm/module.config.jsx:73 |
| Mode sombre | classe `.dark` sur `<html>` + `data-theme` + `color-scheme` + meta theme-color ; `'system'` suit l'OS ; bascule animée 200 ms | design/theme.js:62-90 ; tokens.css:406 |
| Autres modes | `[data-density='comfortable'/'compact']` (hauteurs `--control-h*` 2,5/2/2,75 rem) ; `data-sunlight='1'` (plein soleil, ombres à `none`) | tokens.css:562-660 |
| Polices | Archivo (titres, `font-display`), Hanken Grotesk (corps, `font-brand`), Sora ; woff2 auto-hébergés `public/fonts/` ; Noto Sans Arabic chargé à la demande (RTL) | tokens.css:29-30 ; public/fonts |
| Échelle texte | display 3 / h1 2,25 / h2 1,75 / h3 1,375 / body 1 / small 0,875 / caption 0,75 rem, avec lh et letter-spacing | tokens.css:307-313 |
| Rayons | `--radius` 0,625 rem ; sm/md/lg/xl dérivés | tokens.css:299, 540-543 |
| Ombres | `--shadow-xs/sm/md/lg`, élévations nommées `card, card-hover, menu, modal, toast`, `--shadow-focus-ring` ; version sombre redéfinie | tokens.css:323-342, 498-501, 552-557 |
| Z-index | échelle `--z-sticky-raised 1150 / overlay 1200 / modal 1300 / popover 1400 / toast 1500` | tokens.css:~385 |
| Mouvement | `--motion-fast 120 / base 180 / slow 260 / pulse 350 ms`, `--ease-standard cubic-bezier(.4,0,.2,1)` ; keyframes `slide-in-*`, `pop-in`, `fade-in`, `accordion-*`, `badge-pulse`, `stat-solidify`, `field-saved-pulse` | tokens.css:395-405, 738-910 |
| Reduced motion | RESPECTÉ : durées tombent à 0 ms sous `prefers-reduced-motion` ; en plus un réglage app `data-reduced-motion="true"` ; hook `hooks/usePrefersReducedMotion.js` | tokens.css:1047-1057 ; lib/apps/appTransition.js:22-30 |
| Espacements | pas d'échelle propre : Tailwind 4 natif | (non trouvé de token) |
| « Pas de couleur en dur » | `npm run check-hex` = `scripts/check_hex.mjs` : scanne UNIQUEMENT `src/index.css` résolu (ses `@import`), et seulement une liste `GUARDED_SELECTORS` de blocs déjà tokenisés (`.modal`, `.data-table`, `.empty-state`…). `tokens.css` exempté. Ailleurs (JSX, nouvelles feuilles) : pas de garde automatique, mais convention forte. Un nouveau CSS Tâches doit être ajouté à la liste pour être protégé. | check_hex.mjs:1-50 |

## 2. Primitives `src/ui/` (barrel `src/ui/index.js`, 79 l.)
Toutes dessus **Radix** + **cva** + `cn` (clsx+tailwind-merge) + **lucide-react**. Import : `import { Button } from '@/ui'`.

| Primitive | API / comportement | Preuve |
|---|---|---|
| Button | variants `default`(primaire laiton, ombre teintée), secondary, outline, ghost, destructive, success, link ; tailles sm/md/lg/icon/icon-sm ; `loading`, `asChild` ; hauteurs via `--control-h*` | Button.jsx:28-56 |
| IconButton, Spinner, Badge(`tone`), Tag(`onRemove`), StatusPill(`status/tone/dot`) | existent | ui/*.jsx |
| Dialog / AlertDialog / ConfirmDialog | Radix ; `ConfirmDialog` + `useConfirmDialog` (`ui/confirm.jsx`) styles `destructive` | ConfirmDialog.jsx:43 |
| Sheet | Radix Dialog ; `side` right/left/**bottom**/top ; bottom = `max-h-[85vh] rounded-t-2xl` ; glisser-vers-le-bas pour fermer (seuil distance OU vélocité, seulement si contenu à `scrollTop===0`) ; **pas de crans (snap points)** | Sheet.jsx:14-60 |
| ResponsiveDialog | `<768 px` → Sheet bas, `≥768` → Dialog centré ; mêmes props `open/onOpenChange/title/description/footer` ; hook `useIsMobile` | ResponsiveDialog.jsx:19-37 |
| DatePicker / DateRangePicker | popover calendrier maison ; navigation clavier (`focusDate`) ; `min/max/clearable`, format `jj/mm/aaaa`. **Aucun raccourci « demain/lundi »** | DatePicker.jsx:157-175 |
| TimePicker, Combobox (`forwardRef`, ARIA activedescendant), Select (Radix), MultiSelect, Segmented (radiogroup, flèches/Home/End, tailles md/sm), Tabs (Radix), Switch, Checkbox (coche avec `animate-pop-in`, press), RadioGroup, Slider, Progress, ChecklistProgress | existent | ui/*.jsx |
| EmptyState | `icon` ou `illustrated` (pictogramme solaire SVG), `tone` neutral/error/warning, `title/description/action` | EmptyState.jsx:53 |
| Skeleton | `Skeleton, SkeletonLine, SkeletonText, SkeletonAvatar, SkeletonCard, SkeletonTableRow` ; + `SqueletteLignesCarte`, `ChargementPage`, `EtatListe`, `OfflineState`, `FadeSwap` | Skeleton.jsx |
| Toaster | **sonner** ; `bottom-right`, icônes lucide, un registre par type (tokens) ; UN seul monté dans `components/ShellGlobal.jsx:37` | Toaster.jsx:36-73 |
| Tooltip/Popover/HoverCard/DropdownMenu/ContextMenu | Radix, stylés | ui/*.jsx |
| FloatingActionButton | `position:fixed`, au-dessus de la tabbar, safe-area, **mobile seulement (<768)** ; props `label, icon, onClick` | FloatingActionButton.jsx:1-38 |
| Form / FormField / FormErrorSummary, `useDirtyGuard`, `useFormSafety`, `useDraftAutosave(key, snapshot, {enabled, version})` (localStorage débouncé 800 ms) | existent | useDraftAutosave.js:1-30 |
| `usePullToRefresh` (+ `IndicateurTirerPourActualiser`) | maison, sans dépendance, seuil + amortissement | usePullToRefresh.js:1-30 |
| Autres utiles | `Stat`, `Card`, `StatusAccentCard`, `NextActionBanner`, `MenuActionsLigne`, `CelluleCalendrier`, `kanbanAffectation`, `DictationButton`, `PageHeader` | ui/ |

**Page de démonstration : OUI**, route `/ui` (`router/index.jsx:434`) → `pages/ui/UIShowcase.jsx` (jetons, kit, densité, boutons, badges, sélecteurs, undo, tuiles d'app). `pages/ui/DataTableDemo.jsx` aussi.

**Bibliothèques réellement présentes** (`package.json`) : react ^19.3.1, react-router-dom ^7.18.5, Tailwind ^4.2.4 (+`@tailwindcss/vite`), vite ^8.3.6, vite-plugin-pwa ^1.3.0, Radix (accordion, alert-dialog, avatar, checkbox, context-menu, dialog, dropdown-menu, hover-card, label, popover, progress, radio-group, scroll-area, select, separator, slider, slot, switch, tabs, tooltip — tous ^1.x/2.x), class-variance-authority ^0.7.1, clsx ^2.1.1, tailwind-merge ^3.7.0, lucide-react ^1.70.0, sonner ^2.0.8, @dnd-kit/core ^6.3.1, @tanstack/react-table ^8.21.3, recharts ^2.15.3, @reduxjs/toolkit ^2.14.0, axios, maplibre-gl, leaflet, three, pdfjs-dist, @sentry/react.
**ABSENTES** : framer-motion/motion, vaul, cmdk, Headless UI, @dnd-kit/sortable, @dnd-kit/utilities, date-fns/dayjs (`ui/date-utils.js` maison), react-big-calendar/fullcalendar. (Grep `framer-motion|vaul|cmdk` : seules des occurrences de « cmdk » comme nom de classe/clé.) La palette de commandes est maison (`GlobalSearch.jsx`).

## 3. Mouvement et gestes
- **Animation** : CSS pur (keyframes tokens + `transition`). Transition d'app ↔ accueil : View Transitions API avec repli `.route-fade`, instantanée si reduced-motion, sans dépendance (`lib/apps/appTransition.js:1-40`).
- **Glisser-déposer** : uniquement `@dnd-kit/core` (10 imports, AUCUN `sortable`). Utilisé : `pages/crm/leads/views/KanbanView.jsx`, `ForecastView.jsx`, `pages/installations/views/KanbanView.jsx`, `PlanificationPage.jsx`, `InterventionsPage.jsx`, `sav/TicketCalendarView.jsx`, `home/HomeMenu.jsx`, `features/uxviews/FavorisWidget.jsx`. Réglage tactile de référence : `PointerSensor {distance:6}` + `TouchSensor {delay:150, tolerance:8}` + `KeyboardSensor` (FavorisWidget.jsx:115-118) ; CSS `touch-action: manipulation` sur kanban (23-kanban.css:177). Clavier/lecteur d'écran : `features/kanban/kanbanA11y.js`, `features/uxviews/dndA11y.js`.
- **Balayage sur ligne** : code maison, PAS un composant partagé. `ui/datatable/DataTable.jsx` (`useSwipeReveal`, `swipeActions`, révélation + snap) ; la version carte-lead (VX43/LB17) a été RETIRÉE (`LeadCard.jsx:58`). Test `DataTableSwipeAction.test.mjs`.
- **Haptique** : `lib/haptics.js` `hapticTap(10)` (feature-detect, muet sur iOS Safari) ; aussi `KanbanView.jsx:313`.
- **Tirer pour rafraîchir** : `usePullToRefresh`, existe, utilisé (Ma journée, Interventions, kanban).
- **Fête** : `ui/celebrate.js` (canvas + Web Audio, 35 s) réservée à « affaire signée » ; rien de discret pour une simple complétion.

## 4. Coquille et mise en page
- `components/layout/` : `Layout, Sidebar, Header, BottomTabBar, AppLauncher, Breadcrumbs, GlobalSearch, NotificationBell…`.
- **BottomTabBar** : plafond dur 5 onglets (`MAX_TABS=5`), 1 = « Apps » (sortie), donc 4 pour l'app ; au-delà de 4 sections → 3 directes + « Plus » (tiroir) ; `splitAppTabs` pur. Une app y place ses entrées via `nav.items` de son `module.config.jsx` (ex. `features/crm/module.config.jsx:91`, `{to,label,k,icon,roles}`). Hors app, barre absente. (BottomTabBar.jsx:23-60)
- Mobile = `<768 px` (`.bottom-tabbar` 52 px + zone sûre) ; rupture dominante `max-width:768px` (25 usages) ; autres 900/1024/1100.
- Zones sûres : `env(safe-area-inset-*)` dans 56 occurrences ; en-tête 52 px + encoche, `.layout-content` dégage 64 px de nav basse (`mobile-foundation.test.mjs:61-90`).
- Clavier virtuel : `hooks/useKeyboardAwareScroll.js` (visualViewport, ramène le champ actif au centre).
- `features/pwa/ios-polish.test.mjs` verrouille : `viewport-fit=cover`, barre d'état translucide, mode app installée, theme-color de repli, écrans de démarrage, `overscroll-behavior:contain` + inertie iOS.
- Densité : `data-density` comfortable/compact (voir §1).

## 5. Les écrans les plus soignés
1. **Cockpit du lead** `features/crm/workspace/` (`LeadWorkspace`, `IdentityRail`, `ContextRail`, `SectionsPane`, `StageControl`, `TimelineTab`) : rail d'identité + rail de contexte + sections, squelette dédié (`LeadWorkspace.skeleton.test.jsx`), raccourcis clavier, chatter. À réutiliser : le patron « fiche + fil d'activité » pour la fiche tâche.
2. **`/ma-journee`** (installations, `module.config.jsx:81,104`) : liste du jour terrain, tirer-pour-rafraîchir, FAB, bandeau « Prochaine action » (`NextActionBanner`). Patron direct pour « Aujourd'hui ».
3. **`/apps` HomeMenu** (`pages/home/HomeMenu.jsx`, 31-menu-apps.css) : tuiles avec `--shadow-tile`, réorganisation par `@dnd-kit`, transitions d'app. `MesActivitesPage` (656 l.) : `EmptyState`, `Spinner`, filtres — fonctionnel mais dense.
- **`/calendrier`** (`pages/CalendarPage.jsx`, 310 l.) : code MAISON, pas de bibliothèque d'agenda. Une seule vue : grille MOIS (`components/MonthGrid.jsx`, 128 l.). Replanifier = glisser-déposer **HTML5 natif** (`draggable`, `onDrop`, :205) — donc **inutilisable au doigt** — suivi d'un `confirm()` nommé (:161-185). Pas de vue semaine/jour/agenda, pas d'heures. Abonnement iCal (lien régénérable). Qualité mobile : faible (puces dans une grille). **Ne pas en hériter pour Tâches.**

## 6. Contraintes qui mordent
- **ESLint** (`eslint.config.js`) : `no-unused-vars` (hors `^[A-Z_]`), react-hooks 7, react-refresh (désactivé dans `ui/`, `lib/`, `module.config.jsx`, tests). `no-alert` interdit seulement sur parametres/approbations ; garde « catch vide autour d'await » sur 8 écrans facturation. `npm run lint` = `eslint . && node scripts/check_no_danger.mjs` (interdit `dangerouslySetInnerHTML` hors `renderTrustedSvg`).
- **`data-testid`** : kebab-case libre (`approbations-attention-card`, `annonces-liste`…). `e2eHooks.test.mjs` ne verrouille que Calepinage (`features/calepinage/E2E_HOOKS.md`) ; la règle « hooks DOM = contrat » est en mémoire utilisateur (non revérifiée ici).
- **Un seul `<Toaster>`** : `ShellGlobal.jsx:37`. Utiliser `toast` de `ui/Toaster`.
- **Cible tactile** : pas de règle ESLint ni de test trouvés ; seuls repères : `--control-h` 2,5 rem (40 px) en confortable, 2,75 rem pour `lg` ; `34-pouce-ody.css` = zone du pouce. (Aucun 44 px imposé — non trouvé.)
- **Captures** : `e2e/visual.spec.js` `toHaveScreenshot` tag `@visual`, seuil 2 % (`maxDiffPixelRatio`), clair+sombre, en `release-verify` (pas par merge). Une nouvelle page Tâches n'y entre que si on l'ajoute. Axe-core (`@axe-core/playwright`, `vitest-axe`) présent ; `ui/contrast.test.mjs`.
- **Budget bundle** : `scripts/check_bundle_budget.mjs` : 350 Ko gzip par chunk, total 3 815 Ko gzip (l.5, 208). Nouvelle dépendance = contrôlée par cela, et par la règle maison.
- **i18n** : catalogues `i18n/catalogs/{fr,en,ar}.json`, `useT()` ; usage réel limité (le grep compte 7 fichiers pages/features avec `useT` sur ~731 `.jsx` hors tests). Le gros du texte est du français en dur ; le catalogue sert surtout au chrome (nav). `i18n-coverage.test.mjs` exige les 3 catalogues synchrones en clés. → Pour Tâches : clés dans les 3 catalogues pour la navigation ; le reste en français comme les autres écrans (choix par défaut).
- **Multi-onglet/RTL** : `RtlDirectionProvider` existe ; utiliser des propriétés logiques (`ms-/me-`).

## 7. Manques et plus petit ajout
| Manque | État | Plus petit ajout |
|---|---|---|
| Ligne balayable partagée | maison dans DataTable seulement | extraire `useSwipeReveal` de `DataTable.jsx` en `ui/SwipeRow.jsx` (sans dépendance) |
| Case animée « cocher » | `Checkbox` a `pop-in` seul | ajouter variante ronde + barré animé en CSS (keyframe + token `--motion-base`) |
| Sélecteur de date intelligent | `DatePicker` pur calendrier | rangée de puces Aujourd'hui/Demain/Lundi/+1 sem. au-dessus (calcul dans `date-utils.js`) |
| Grille d'agenda semaine/jour | seulement mois, drag HTML5 | grille CSS maison ; glisser avec `@dnd-kit/core` déjà installé (TouchSensor) |
| Kanban générique | 3 kanban spécifiques + `kanbanA11y` | extraire un `Board` des patrons Leads/Installations |
| Feuille du bas à crans | Sheet 85 vh + fermeture par glisser | 2 hauteurs via CSS + le geste existant ; sinon vaul (à éviter) |
| Champ à jetons surlignés (dates/#tags dans la saisie) | aucun | `contenteditable`/overlay maison ; analyse déterministe dans `lib/` |
| Anneau de progression | `Progress` (barre), `ChecklistProgress` | SVG circulaire ~30 lignes sur tokens |
| Succès discret | `celebrate.js` = 35 s, réservé aux signatures | micro-pulse CSS (`field-saved-pulse` réutilisable) + `hapticTap` |
| Réordonner une liste | `@dnd-kit/core` sans `sortable` | réordonner à la main avec `useDraggable/useDroppable` (déjà fait dans `ViewsManagerPopover`) ; `@dnd-kit/sortable` seulement si pénible (petite dépendance sœur) |
| Annuler (undo) toast | section « undo » de `/ui` | réutiliser |

**Aucune nouvelle dépendance n'est nécessaire** pour tout ce qui précède.

## Choix par défaut
- Pas de framer-motion/vaul/cmdk : CSS + `@dnd-kit/core` suffisent (règle maison, budget bundle).
- Écrans Tâches construits UNIQUEMENT avec `ui/` + tokens ; toute nouvelle feuille CSS ajoutée à `GUARDED_SELECTORS` de `check_hex.mjs`.
- Mobile = `<768 px` ; FAB + `ResponsiveDialog` pour la saisie ; barre d'onglets ≤4 entrées.
