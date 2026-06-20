# Système de design Taqinor OS — référence canonique (F14 + P69)

> **Fichier de référence unique** de la refonte UI « plus beau qu'Odoo ».
> Documente le système de tokens, le thème, la densité, le mouvement,
> l'élévation, les polices et le catalogue des primitifs `src/ui/*`.
> Source de vérité des tokens : [`frontend/src/design/tokens.css`](../../frontend/src/design/tokens.css).
> Tenir à jour quand un token est ajouté/renommé ou qu'un primitif évolue.
> Pour les captures d'écran avant/après, voir [`SCREENSHOTS.md`](./SCREENSHOTS.md).

---

## 1. Marque Taqinor (extraite de `apps/web`)

Le site public `apps/web` est la source de vérité de l'identité. La refonte de
l'ERP reprend **les mêmes polices et la même palette** pour une marque unifiée.

L'or laiton est **l'accent, utilisé avec parcimonie** (CTA clés, focus en
sombre) ; la base neutre est l'encre/nuit + gris azurés. On évite les looks
« IA par défaut » (crème+terracotta serif ; quasi-noir+vert acide ; filets de
journal).

---

## 2. Modèle de tokens à 3 couches

Défini dans `frontend/src/design/tokens.css` (Tailwind v4, directives `@theme`).

```
Primitives (palette de marque, fixe)
  brass / nuit / encre / azur / lune
        │  @theme  →  utilitaires bg-brass-400, text-nuit…
        ▼
Sémantique (rôles, thémables runtime clair/sombre)
  --background --foreground --primary --destructive --success …
        │  @theme inline  →  bg-background, text-foreground, border-border…
        ▼
Composant (consommé par /src/ui/* et les écrans migrés)
  Button, Input, DataTable… utilisent UNIQUEMENT les utilitaires sémantiques
```

### Couche 1 — Primitives (bloc `@theme`)

Palette brute de marque. Valeurs fixes, ne change pas selon le thème.

| Famille | Tokens | Hex |
|---------|--------|-----|
| **Brass** (accent énergie solaire) | `brass-50` → `brass-700` | `#fdf8ec` `#faedc8` `#f6dd94` `#f3cc66` `#e8b54a` `#d39a2c` `#8f6a0e` `#6f520b` |
| **Nuit / Encre** (base neutre profonde) | `nuit`, `nuit-800`, `nuit-700`, `encre`, `encre-soft`, `encre-faint` | `#070b1d` `#0b1226` `#101a3c` `#0c1335` `#3f4a6e` `#5a6488` |
| **Azur** (bleus de marque) | `azur-100/200/600/700/900/950` | `#dde5f8` `#b9c8f0` `#2342b5` `#1c3494` `#0f1c54` `#0a1238` |
| **Lune** (gris froids clairs) | `lune`, `lune-soft`, `lune-faint` | `#d6dbe9` `#adb5cd` `#8d96b4` |

Utilitaires Tailwind générés : `bg-brass-400`, `text-nuit`, `border-azur-600`…
(à réserver aux cas où aucun rôle sémantique ne convient).

### Couche 2 — Sémantique (rôles thémables)

Variables runtime définies en clair sur `:root` puis surchargées sur `.dark`.
Mappées en utilitaires Tailwind via `@theme inline` (donc thémables sans
recompilation) : `--color-<rôle>: var(--<rôle>)`.

| Rôle sémantique | Variable | Utilitaire Tailwind | Clair (`:root`) | Sombre (`.dark`) |
|-----------------|----------|---------------------|-----------------|------------------|
| Fond de page | `--background` | `bg-background` | `#f6f8fc` | `#070b1d` |
| Texte par défaut | `--foreground` | `text-foreground` | `#0c1335` | `#e7ecf6` |
| Surface / carte | `--surface` (alias hist. de `--card`), `--card` | `bg-surface`, `bg-card` | `#ffffff` | `#0b1226` |
| Texte sur carte | `--card-foreground` | `text-card-foreground` | `#0c1335` | `#e7ecf6` |
| Popover | `--popover`, `--popover-foreground` | `bg-popover` | `#ffffff` | `#0b1226` |
| **Primary** (or laiton) | `--primary`, `--primary-foreground` | `bg-primary text-primary-foreground` | `#e8b54a` / `#1a1505` | `#f3cc66` / `#1a1505` |
| Secondary | `--secondary`, `--secondary-foreground` | `bg-secondary` | `#eef2fb` / `#0f1c54` | `#101a3c` / `#d6dbe9` |
| Muted | `--muted`, `--muted-foreground` | `bg-muted text-muted-foreground` | `#eef1f8` / `#5a6488` | `#101a3c` / `#adb5cd` |
| Accent | `--accent`, `--accent-foreground` | `bg-accent` | `#eef2fb` / `#0f1c54` | `#152870` / `#e7ecf6` |
| **Destructive** | `--destructive`, `--destructive-foreground` | `bg-destructive` | `#b3402a` / `#ffffff` | `#e06a52` / `#1a0a06` |
| **Success** | `--success`, `--success-foreground` | `bg-success` | `#2f7a3f` / `#ffffff` | `#4caf6a` / `#07140a` |
| **Warning** | `--warning`, `--warning-foreground` | `bg-warning` | `#c8870f` / `#1a1505` | `#f3cc66` / `#1a1505` |
| **Info** | `--info`, `--info-foreground` | `bg-info` | `#2342b5` / `#ffffff` | `#7fa0ef` / `#0a1238` |
| Bordure | `--border` | `border-border` | `#dde3f0` | `#1f2a4d` |
| Bordure de champ | `--input` | `border-input` | `#d2d9ea` | `#243156` |
| Anneau de focus | `--ring` | `ring-ring` | `#2342b5` | `#f3cc66` |

> Le `primary` porte un **texte foncé** (`primary-foreground` ≈ `#1a1505`) pour
> garder un contraste AA sur l'or.

### Couche 3 — Composant

Les primitifs `src/ui/*` (et les écrans migrés) ne consomment **que** les
utilitaires sémantiques de la couche 2 (jamais d'hex en dur, jamais de
`dark:`). C'est ce qui rend le thème runtime gratuit.

---

## 3. Thème clair / sombre (F18)

Logique pure dans `frontend/src/design/theme.js` ; provider React dans
`ThemeProvider.jsx` ; bascule dans `ThemeToggle.jsx`.

- **Modes** : `light` / `dark` / `system` (défaut **`system`**, suit l'OS).
- **Persistance** : `localStorage` clé `taqinor-theme` (`THEME_KEY`).
- **`initTheme()`** (appelée au démarrage, ex. `main.jsx`) lit la préférence
  stockée et applique thème + densité avant le premier rendu.
- **`applyTheme(theme)`** résout `system` → `light|dark` via
  `prefers-color-scheme`, puis sur `<html>` :
  - bascule la classe `.dark` (`root.classList.toggle('dark', …)`),
  - pose `style.colorScheme` et l'attribut `data-theme`,
  - met à jour la `<meta name="theme-color">` (`#f6f8fc` clair / `#070b1d` sombre).
- **`subscribeSystemTheme()`** réapplique le thème quand l'OS bascule (si mode
  `system`).
- Les surcharges sombres vivent dans le bloc `.dark { … }` de `tokens.css`.

> **Zéro régression** : les écrans non migrés ont des couleurs en dur ; passer
> en sombre ne les modifie pas — seules les surfaces tokenisées (`/src/ui`)
> réagissent.

---

## 4. Densité (F20)

Attribut `[data-density]` sur `<html>`, posé par `applyDensity()` ; persisté
sous `localStorage: taqinor-density` (`DENSITY_KEY`). Deux modes :
`comfortable` (défaut) et `compact`.

| Variable | Rôle | `comfortable` | `compact` |
|----------|------|---------------|-----------|
| `--control-h` | hauteur des contrôles (boutons, champs) | `2.5rem` | `2rem` |
| `--control-h-sm` | contrôle petit | `2rem` | `1.75rem` |
| `--control-h-lg` | contrôle grand | `2.75rem` | `2.375rem` |
| `--control-px` | padding horizontal des contrôles | `0.875rem` | `0.625rem` |
| `--field-gap` | espace vertical entre champs | `0.75rem` | `0.5rem` |
| `--row-py` | padding vertical des lignes de tableau | `0.625rem` | `0.375rem` |
| `--ui-text` | taille de texte UI | `0.9375rem` (15px) | `0.875rem` (14px) |

Les primitifs lisent ces vars (ex. `Button` : `h-[var(--control-h)]`,
`px-[var(--control-px)]`), donc tout s'adapte sans variante par composant.

---

## 5. Mouvement (motion)

| Token | Valeur | Usage |
|-------|--------|-------|
| `--motion-fast` | `120ms` | sorties / micro-interactions |
| `--motion-base` | `180ms` | entrées d'overlay / transitions standard |
| `--motion-slow` | `260ms` | transitions amples |
| `--ease-standard` | `cubic-bezier(0.4, 0, 0.2, 1)` | courbe par défaut |

Animations d'overlay (Dialog/Popover/Dropdown/Tooltip) déclarées en `@theme` :
`--animate-overlay-in/out` (keyframes `overlay-in/out`) et
`--animate-pop-in/out` (keyframes `pop-in/out`).

**`prefers-reduced-motion: reduce`** ramène `--motion-fast/base/slow` à `0ms`
(via `@media` sur `:root`), donc toutes les transitions tokenisées
disparaissent pour les utilisateurs sensibles.

---

## 6. Élévation / ombres

Quatre niveaux, teintés à l'encre en clair et au noir en sombre.

| Variable | Utilitaire | Usage |
|----------|------------|-------|
| `--shadow-xs` | `shadow-ui-xs` | boutons, hover léger |
| `--shadow-sm` | `shadow-ui-sm` | cartes, inputs surélevés |
| `--shadow-md` | `shadow-ui-md` | popovers, dropdowns |
| `--shadow-lg` | `shadow-ui-lg` | dialogs, sheets |

Mappés en utilitaires Tailwind via `@theme inline` (`--shadow-ui-*`). Les
valeurs sombres sont plus opaques (noir 40–65 %) pour rester lisibles.

Rayons : `--radius` (`0.625rem`) → `radius-sm` (−4px), `radius-md` (−2px),
`radius-lg` (=), `radius-xl` (+4px).

---

## 7. Z-index (échelle unique)

Une seule échelle pour éviter les guerres de `z-index`.

| Variable | Valeur | Couche |
|----------|--------|--------|
| `--z-base` | `0` | contenu |
| `--z-dropdown` | `1000` | menus déroulants |
| `--z-sticky` | `1100` | en-têtes/colonnes collantes |
| `--z-overlay` | `1200` | voile d'arrière-plan |
| `--z-modal` | `1300` | dialogs |
| `--z-popover` | `1400` | popovers |
| `--z-toast` | `1500` | notifications toast |

---

## 8. Polices de marque

Déclarées en `@theme` :
- **`--font-display`** → **Archivo** (titres / display ; utilitaire
  `font-display`).
- **`--font-brand`** → **Hanken Grotesk** (corps / UI ; utilitaire
  `font-brand`).

Auto-hébergées dans `frontend/public/fonts/` (`archivo-*.woff2`,
`hanken-*.woff2`), **préchargées** dans `frontend/index.html` (anti-FOUT) :

```html
<link rel="preload" href="/fonts/hanken-latin.woff2" as="font" type="font/woff2" crossorigin />
<link rel="preload" href="/fonts/archivo-latin.woff2" as="font" type="font/woff2" crossorigin />
<link rel="stylesheet" href="/fonts/brand.css" />
```

On **ne touche pas** au `--font-sans` par défaut de Tailwind ni à la police
globale du `<body>` : additif, sans régression. La classe `.ui-root` applique
`font-family: var(--font-brand)`.

Chiffres **tabulaires** (`.tabular-nums` → `font-variant-numeric: tabular-nums`)
pour tout montant / quantité (alignement des colonnes).

---

## 9. Catalogue des primitifs (`frontend/src/ui/*`)

Point d'entrée unique : `import { Button, Input, Dialog } from '@/ui'`
(`src/ui/index.js`). Vitrine vivante sur la route **`/ui`** (`UIShowcase`).

**Définition de « terminé » (DoD) commune à tout primitif** : états visibles
(hover / active / disabled / loading / focus-visible), conforme en clair **et**
sombre via tokens sémantiques, navigable au **clavier**, sémantique **ARIA**
correcte, anneau de focus `ring-ring`, aucune couleur en dur.

### Base / affichage
| Primitif | Rôle | DoD spécifique |
|----------|------|----------------|
| `Button` | bouton (variants `default/secondary/outline/ghost/destructive/success/link`, tailles `sm/md/lg/icon`) | `loading` (Spinner + `aria-busy`), `disabled`, `asChild` (Slot), `focus-visible:ring-ring ring-offset-background` |
| `IconButton` | bouton icône carré | `aria-label` requis, mêmes états que Button |
| `Spinner` | indicateur de chargement | `role`/label accessible |
| `Badge` | étiquette de ton (`badgeVariants` : neutral/primary/info/success/warning/danger/outline) | contraste AA par ton, clair+sombre |
| `Tag` | étiquette/chip, parfois supprimable | bouton de suppression au clavier, `aria-label` |
| `StatusPill` | **taxonomie de statut unique** (leads/devis/factures/chantiers/SAV) → ton + point coloré | la couleur n'est jamais le seul signal (point `aria-hidden`), `tone` explicite l'emporte sur `statusTone(status)` |
| `Avatar` | avatar / initiales fallback | `alt`, fallback si image absente |
| `Stat` | KPI (valeur + label + tendance) | `tabular-nums`, ton de tendance |
| `Card` | conteneur surface (`Card`/Header/Title/Content/Footer) | `bg-card text-card-foreground border-border` |
| `Separator` | séparateur horizontal/vertical | `role="separator"`, orientation ARIA |
| `Skeleton` | placeholder de chargement | `aria-hidden`, animation respecte reduced-motion |
| `Progress` | barre de progression | `role="progressbar"` + `aria-valuenow/min/max` |
| `DefinitionList` | paires clé/valeur (fiches) | sémantique `<dl>/<dt>/<dd>` |
| `EmptyState` | état vide (illustration + action) | titre, action focusable |
| `NotFound` | écran 404 | lien retour focusable |
| `OfflineState` | état hors-ligne | message + action de réessai |
| `ErrorBoundary` | capture d'erreur React | fallback accessible, reset |

### Formulaire / contrôles
| Primitif | Rôle | DoD spécifique |
|----------|------|----------------|
| `Label` | label de champ | `htmlFor`, indicateur requis |
| `Input` | champ texte (hauteur `--control-h`) | états error/disabled, `aria-invalid`, `border-input` + `ring-ring` au focus |
| `Textarea` | zone de texte multi-lignes | autosize/min-rows, mêmes états qu'Input |
| `NumberInputs` | champs numériques (montants/quantités) | `tabular-nums`, `inputMode`, jamais de snap/reject (cohérent avec `step="any"` du générateur de devis) |
| `Checkbox` | case à cocher (Radix) | états checked/indeterminate, clavier (Espace), `aria-checked` |
| `Switch` | interrupteur (Radix) | `role="switch"`, clavier, `aria-checked` |
| `RadioGroup` | groupe radio (Radix) | navigation flèches, `aria-checked` |
| `Slider` | curseur (Radix) | flèches/PageUp/Down, `aria-valuenow` |
| `Segmented` | contrôle segmenté (toggle group) | flèches, état actif, `role`/aria |
| `Select` | liste déroulante (Radix Select) | clavier (flèches/Entrée/Échap), `aria-expanded`, overlay animé |
| `Combobox` | sélection avec recherche (single) | filtrage, navigation clavier, `aria-activedescendant`, vide géré |
| `MultiSelect` | sélection multiple avec recherche + tags | ajout/retrait clavier, annonce des sélections |
| `DatePicker` | calendrier de date (fr-FR) | navigation clavier dans la grille, `aria-label` des jours |
| `TimePicker` | sélection d'heure | clavier, format 24h |
| `FileUpload` | dépôt/sélection de fichiers (drag&drop) | input accessible, états drag/erreur, liste des fichiers |
| `Form` + `useDirtyGuard` | wrapper de formulaire + garde « modifs non enregistrées » | messages d'erreur liés (`aria-describedby`), garde de navigation |

### Overlays
| Primitif | Rôle | DoD spécifique |
|----------|------|----------------|
| `Dialog` | modale centrée (Radix) | focus trap, Échap, `aria-modal`, voile `--z-overlay`/contenu `--z-modal`, animation `overlay/pop` |
| `Sheet` | panneau latéral (Radix Dialog) | mêmes garanties que Dialog, glisse depuis un bord |
| `AlertDialog` | confirmation destructive (Radix) | focus par défaut sur Annuler, `role="alertdialog"` |
| `Popover` | popover ancré (Radix) | placement, Échap, clic extérieur, `--z-popover` |
| `Tooltip` | infobulle (Radix) | délai, clavier (focus), `role="tooltip"` |
| `DropdownMenu` | menu d'actions (Radix) | navigation flèches, raccourcis, `role="menu"` |
| `HoverCard` | aperçu au survol (Radix) | délai, accessible au focus |
| `ContextMenu` | menu contextuel (clic droit, Radix) | clavier, `role="menu"` |

### Feedback / navigation
| Primitif | Rôle | DoD spécifique |
|----------|------|----------------|
| `Toaster` | notifications toast | empilement, auto-dismiss, `role="status"`/`aria-live`, `--z-toast` |
| `Tabs` | onglets (Radix) | flèches, `aria-selected`, panneaux liés |
| `Accordion` | sections repliables (Radix) | clavier, `aria-expanded` |

### Données / listes (Groupe H — moteur `datatable/`)
| Export | Rôle | DoD spécifique |
|--------|------|----------------|
| `DataTable` + `useDataTable` | moteur de table réutilisable (tri, pagination, sélection) | en-tête triable au clavier, `aria-sort`, lignes sélectionnables, colonnes collantes via `--z-sticky` |
| `EditableCell` | édition inline d'une cellule | entrée/Échap, focus, validation |
| `BulkActionBar` | barre d'actions sur sélection | annonce du nombre sélectionné, actions focusables |
| `ColumnManager` | affichage/ordre des colonnes | clavier, état persisté |

---

## 10. Comment consommer (règles d'or)

1. **Toujours les utilitaires sémantiques**, jamais d'hex en dur :
   `bg-card text-foreground border-border`, `bg-primary text-primary-foreground`,
   `text-muted-foreground`, `ring-ring`. **Pas** de `bg-[#0c1335]`.
2. **Pas de `dark:`** dans le code applicatif : le thème vient des tokens
   runtime (la classe `.dark` surcharge les variables, les utilitaires
   sémantiques suivent automatiquement).
3. **Wrapper `.ui-root`** sur les écrans/sections migrés (applique
   `--font-brand`, `--background`, `--foreground`, `--ui-text`) — sans l'imposer
   aux écrans non encore migrés.
4. **`.tabular-nums`** sur tout montant, quantité ou colonne chiffrée.
5. **Réutiliser les primitifs** `@/ui` plutôt que recréer boutons/champs/overlays.
6. **Statuts** : passer par `StatusPill` (taxonomie unique) ; ne pas réinventer
   les correspondances couleur.
7. **Hauteurs/espacements** : laisser les primitifs lire `--control-h`,
   `--field-gap`, `--row-py` (ne pas figer en `px`).
8. **Z-index** : utiliser l'échelle `--z-*`, jamais de valeur arbitraire.

---

## 11. Principe d'adoption — ZÉRO régression

La couche design est **100 % additive** : tokens à noms personnalisés, aucun
défaut Tailwind écrasé, police globale du `<body>` inchangée, aucun `dark:`
ailleurs dans l'app. Les écrans existants restent **identiques** tant qu'ils ne
sont pas migrés. La migration se fait écran par écran (groupe J) en remplaçant
les couleurs en dur par les tokens sémantiques, puis en supprimant les `.css`
ad hoc (P67).

### Mapping des `.css` existants → tokens (P67, à venir)
| Fichier .css ad hoc | Tokens / primitifs cibles |
|---------------------|---------------------------|
| `index.css` (body `#f1f5f9`/`#1e293b`, sidebar `#0f172a`) | `--background`/`--foreground`, surface `nuit` |
| `views/kanban.css`, `listview.css`, `charts.css`, `calendar.css` | DataTable (H) + `Card`/`Badge`/`StatusPill` |
| `bulkactionbar.css`, `doublonspanel.css`, `leaddevispanel.css` | primitifs `Button`/`Dialog`/`Card` |
| `parametres.css`, `landing.css` | tokens sémantiques + `Tabs`/`Card` |
| `inlineedit.css`, `assigneepicker.css`, `globalsearch.css`, `notificationbell.css` | `Input`/`Combobox`/`Popover`/`DropdownMenu` |

---

## 12. Fichiers de référence

- **Tokens** : `frontend/src/design/tokens.css`
- **Thème** : `frontend/src/design/theme.js`, `ThemeProvider.jsx`,
  `theme-context.js`, `ThemeToggle.jsx` (tests : `theme.test.mjs`)
- **Polices** : `frontend/index.html` (preload) + `frontend/public/fonts/`
- **Formatage** : `frontend/src/lib/format.js` (MAD, fr-FR, dates, tél. MA)
- **`cn()`** : `frontend/src/lib/cn.js`
- **Primitifs** : `frontend/src/ui/*` (index : `src/ui/index.js`) — vitrine `/ui`
  (`UIShowcase`)
- **Captures avant/après** : [`SCREENSHOTS.md`](./SCREENSHOTS.md)
