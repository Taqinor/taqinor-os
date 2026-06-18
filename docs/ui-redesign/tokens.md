# Refonte UI — Système de tokens & plan de marque (F14 + P69)

> Référence vivante de la refonte « plus beau qu'Odoo ». Couvre l'audit de
> marque (F14) et documente le système de tokens (P69). À tenir à jour à mesure
> que les écrans migrent (groupe J) et que les `.css` ad hoc disparaissent (P67).

## 1. Marque Taqinor (extraite de `apps/web`)

Le site public `apps/web` est la source de vérité de l'identité. La refonte de
l'ERP reprend **les mêmes polices et la même palette** pour une marque unifiée.

### Polices
- **Archivo** — titres / display (`--font-display`), auto-hébergée
  (`frontend/public/fonts/archivo-*.woff2`).
- **Hanken Grotesk** — corps / UI (`--font-brand`), auto-hébergée
  (`hanken-*.woff2`). Préchargées dans `index.html` (anti-FOUT).
- Chiffres **tabulaires** (`.tabular-nums`) pour tout montant / quantité.

### Palette (primitives, `src/design/tokens.css` → `@theme`)
| Rôle | Token | Hex |
|------|-------|-----|
| Accent énergie (or laiton) | `brass-300/400/600` | `#f3cc66` / `#e8b54a` / `#8f6a0e` |
| Base profonde (nuit/encre) | `nuit`, `encre` | `#070b1d`, `#0c1335` |
| Bleus de marque (azur) | `azur-600/950` | `#2342b5` / `#0a1238` |
| Gris froids (lune) | `lune`, `lune-soft` | `#d6dbe9`, `#adb5cd` |
| Succès / Alerte | `ok`, `alert` | `#2f7a3f` / `#b3402a` |

L'or est **l'accent, utilisé avec parcimonie** (CTA clés, focus en sombre) ;
la base neutre est l'encre/nuit + gris azurés. On évite les looks « IA par
défaut » (crème+terracotta serif ; quasi-noir+vert acide ; filets de journal).

## 2. Les trois couches

1. **Primitives** — palette brute de marque (`@theme` → utilitaires
   `bg-brass-400`, `text-nuit`…).
2. **Sémantique** — rôles thémables runtime (`--background`, `--foreground`,
   `--primary`, `--muted`, `--border`, `--ring`, succès/alerte/info…), définis
   en clair sur `:root` et surchargés sur `.dark`. Mappés en utilitaires via
   `@theme inline` → `bg-background`, `text-foreground`, `border-border`,
   `bg-primary text-primary-foreground`…
3. **Composant** — consommée par `src/ui/*` (primitifs shadcn) et les écrans
   migrés.

Échelles complémentaires : `--radius` (sm/md/lg/xl), ombres `--shadow-*`,
z-index `--z-*`, mouvement `--motion-*` (avec `prefers-reduced-motion`).

## 3. Thème (F18) & densité (F20)
- Thème **clair / sombre / système** (défaut **système**), persisté
  (`localStorage: taqinor-theme`), appliqué sur `<html>` (classe `.dark`,
  `color-scheme`, meta `theme-color`). `src/design/theme.js` +
  `ThemeProvider` + `ThemeToggle`.
- **Densité** comfortable (défaut) / compact via `data-density` sur `<html>`
  (`--control-h`, `--row-py`, `--field-gap`, `--ui-text`).

## 4. Principe d'adoption — ZÉRO régression
La couche design est **100 % additive** : noms de tokens personnalisés, aucun
défaut Tailwind écrasé, **police globale du `<body>` inchangée**, aucun `dark:`
utilisé ailleurs dans l'app. Les écrans existants restent **identiques** tant
qu'ils ne sont pas migrés. La migration se fait écran par écran (groupe J) en
remplaçant les couleurs en dur par les tokens sémantiques, puis en supprimant
les ~15 `.css` ad hoc (P67).

## 5. Plan de mapping des `.css` existants → tokens (P67, à venir)
| Fichier .css ad hoc | Tokens cibles |
|---------------------|---------------|
| `index.css` (body `#f1f5f9`/`#1e293b`, sidebar `#0f172a`) | `--background`/`--foreground`, surface `nuit` |
| `views/kanban.css`, `listview.css`, `charts.css`, `calendar.css` | DataTable (H) + `Card`/`Badge`/`StatusPill` |
| `bulkactionbar.css`, `doublonspanel.css`, `leaddevispanel.css` | primitifs `Button`/`Dialog`/`Card` |
| `parametres.css`, `landing.css` | tokens sémantiques + `Tabs`/`Card` |
| `inlineedit.css`, `assigneepicker.css`, `globalsearch.css`, `notificationbell.css` | `Input`/`Combobox`/`Popover`/`DropdownMenu` |

## 6. Fichiers de référence
- Tokens : `frontend/src/design/tokens.css`
- Thème : `frontend/src/design/theme.js`, `ThemeProvider.jsx`, `ThemeToggle.jsx`
- Formatage : `frontend/src/lib/format.js` (MAD, fr-FR, dates, tél. MA)
- `cn()` : `frontend/src/lib/cn.js`
- Primitifs : `frontend/src/ui/*` — vitrine `/ui` (style guide, P68)
