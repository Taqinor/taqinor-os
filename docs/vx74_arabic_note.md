# VX74 — Note chiffrée : l'arabe, interface complète ou langue de documents ?

**Statut : DÉCISION seulement — aucun fichier produit modifié.** Cette note répond à
VX74 (`docs/PLAN2.md`) : chiffrer le coût d'un AR-UI complet vs conserver AR
comme langue de documents, et recommander une voie.

## Constat vérifié dans le repo (2026-07-11)

- Le sélecteur EN/AR (N93) traduit ~121 clés de chrome (menus, titres, labels).
  C'est ~2 % de la surface texte de l'app : `frontend/src` compte 636 fichiers
  `.js/.jsx` hors tests pour ~130 200 lignes de code — le contenu RÉEL des
  pages (formulaires, tableaux, messages, aide) n'est traduit nulle part.
- **RTL CSS : une seule règle existe** — `[dir="rtl"] body { text-align: right; }`
  (`frontend/src/index.css:5219`). Rien d'autre ne réagit à `dir=rtl`.
- **76 fichiers** utilisent des utilitaires Tailwind *physiques* non retournés
  (`ml-*`, `mr-*`, `pl-*`, `pr-*`, `left-*`, `right-*` — vérifié par grep, 74-77
  selon le motif exact). En RTL, `ml-4` reste à gauche au lieu de passer à droite :
  chaque bouton avec icône, chaque tiroir latéral, chaque timeline aurait ses
  marges à l'envers.
- **Aucune primitive UI ne propage `dir`** : `frontend/src/ui/*.jsx` (Dialog,
  DropdownMenu, Drawer/Sheet, Tabs — construits sur Radix) n'a aucun câblage
  `dir={locale === 'ar' ? 'rtl' : 'ltr'}`. Les dropdowns s'ouvriraient toujours
  vers la droite, les tiroirs glisseraient toujours du même côté, sans miroir.
- **Aucune dépendance i18n n'est installée** (`frontend/package.json` : pas de
  `react-intl`/`i18next`/`formatjs`) — le cadre N93 est 100 % maison (3 fichiers
  JSON statiques + surcharges par société). Toute extraction devra être outillée
  à la main ou via un nouvel outil (dépendance à faire approuver).
- **AR existe déjà côté DOCUMENTS**, pas côté UI :
  - `Client.langue_document` (crm migration 0033) modélise déjà le choix par
    client.
  - **XSAL13 est livré** (`docs/DONE.md`) : facture + devis one-page rendus en
    arabe RTL avec police embarquée, quand `langue_document='ar'`.
  - **XSTK18 reste en file** (`docs/PLAN.md`, non construit) : bon de livraison
    + liste de colisage bilingues FR/AR — même patron que XSAL13, pas encore bâti.
  - Les techniciens reçoivent déjà de l'arabe par WhatsApp (QJ4) — un canal
    humain, pas l'UI.

## (a) Taille du dictionnaire à extraire + coût de maintien de 3 catalogues

- **Aujourd'hui (chrome only) :** 121 clés × 3 langues = 363 chaînes. Coût de
  maintien mesuré : ajouter un écran de chrome = 1 ligne × 3 fichiers JSON,
  aucune tierce dépendance, aucun build step (déjà le cas, coût marginal ≈ nul).
- **UI complète (estimation) :** le contenu réel de page (labels de formulaire,
  colonnes de tableau, messages d'erreur/succès, aide contextuelle, texte des
  boîtes de dialogue) est aujourd'hui écrit en dur dans ~636 fichiers pour
  ~130 000 lignes. Une extraction réaliste — en comptant les chaînes UNIQUES
  (beaucoup de labels se répètent : « Enregistrer », « Annuler », noms de
  colonnes) — se chiffre typiquement à **1 500-3 000 clés** pour une app métier
  de cette taille (fourchette usuelle observée sur des ERPs comparables ; à
  affiner par un passage d'extraction automatisée si la voie UI est retenue).
  Cela multiplierait le catalogue par **12× à 25×** sa taille actuelle.
- **Coût de maintien à ce nouveau volume :** chaque nouvelle feature (~1-3
  écrans/semaine au rythme actuel des PLAN2/PLAN runs) ajouterait des dizaines
  de clés × 3 langues à tenir synchronisées ; le garde-fou N93 existant
  (repli silencieux sur FR si une clé manque) masquerait des trous de traduction
  sans alerte — il faudrait AUSSI un lint/CI de couverture i18n (inexistant
  aujourd'hui, à construire) pour éviter la dérive. Sans outillage
  d'extraction (`i18next`/`formatjs`, dépendance externe à faire approuver),
  chaque clé est à la main : risque de dérive élevé, coût récurrent non
  négligeable à chaque plan run touchant le frontend.

## (b) Audit RTL des 76 fichiers physiques→logiques + direction des primitives

- **Fichiers texte/spacing** : convertir `ml-*/mr-*/pl-*/pr-*` → `ms-*/me-*/ps-*/pe-*`
  (Tailwind logical properties, supportées nativement) est mécanique mais pas
  gratuit : chaque conversion doit être visuellement revérifiée (screenshot
  LTR vs RTL) — 76 fichiers, comptez ~10-20 min de revue par fichier en
  incluant les composants à interactions complexes (drag/drop Kanban, Gantt,
  heatmap) = **13-25 h de travail humain/agent + revue**, hors régressions e2e.
- **Primitives Radix (Dialog/DropdownMenu/Drawer-Sheet/Tabs/Select/Combobox/
  DatePicker)** : aucune ne reçoit `dir` aujourd'hui. Il faut : (1) un
  `DirectionProvider` Radix (ou prop `dir` explicite) branché sur
  `useI18n().dir`, (2) revérifier CHAQUE primitive au layout (un `DropdownMenu`
  qui s'ouvre "à droite" en LTR doit s'ouvrir "à gauche" en RTL, un tiroir qui
  glisse depuis la droite doit glisser depuis la gauche). Environ 12 primitives
  partagées (`ui/*.jsx`) + leurs usages spécifiques (icônes directionnelles :
  chevrons, flèches "suivant/précédent", timeline, breadcrumbs) — un audit
  complet, pas un simple flag.
- **Hors périmètre chiffré ici mais à anticiper** : composants tiers non-RTL
  natifs (le générateur de devis, les graphiques, le Gantt de gestion_projet)
  peuvent nécessiter un miroir manuel supplémentaire non couvert par Tailwind
  logical properties seules.
- **Estimation totale audit RTL complet (spacing + primitives + composants
  complexes + revue visuelle) : de l'ordre de 3 à 5 jours-agent pleins** avec
  revue humaine obligatoire (le RTL est un défaut visuel qui ne se détecte pas
  par un test automatique sans captures d'écran comparées).

## (c) Recommandation

**AR = langue de DOCUMENTS seulement, pas UI complète, pas "coquille seulement".**

Raisons :
1. Le champ `Client.langue_document` modélise déjà exactement ce besoin, et
   XSAL13 (facture + devis) est LIVRÉ et fonctionne. XSTK18 (BL/colisage) est
   la suite naturelle, déjà écrite dans le plan, pas encore construite — c'est
   le prochain investissement AR rentable, pas l'UI.
2. Le coût d'une UI complète (12-25× le catalogue actuel + 3-5 jours-agent
   d'audit RTL + maintien récurrent à chaque feature) est disproportionné par
   rapport à l'usage réel observé : les utilisateurs internes de l'ERP
   travaillent en français ; l'arabe sert aux CLIENTS (documents) et aux
   TECHNICIENS terrain (déjà couvert par WhatsApp, un canal humain hors UI).
3. Une « coquille seulement » (menus traduits, contenu non traduit, SANS la
   notice honnête VX73) serait pire que pas d'AR du tout — c'est exactement le
   problème que VX73 vient de corriger pour EN ; l'appliquer aussi à AR sans
   further investissement UI serait revenir en arrière.

**Action recommandée dans le switcher UI (à exécuter séparément, PAS dans cette
tâche zéro-build) :** retirer `ar` de `LOCALES`/`LanguageSwitcher` (ou le
garder mais avec la notice VX73 assumée en continu — au choix de Reda), et
concentrer l'investissement AR sur XSTK18 + tout futur document client/terrain,
où le ROI est prouvé (XSAL13 déjà en prod) plutôt que théorique.

## Chiffres résumés

| Axe | Aujourd'hui (chrome) | UI complète (estimé) |
|---|---|---|
| Clés catalogue | 121 | 1 500 – 3 000 (×12-25) |
| Fichiers RTL à revoir | 0 traité | 76 fichiers spacing + ~12 primitives |
| Effort ponctuel | fait | ~3-5 jours-agent (audit + revue visuelle) |
| Coût récurrent/feature | marginal (1 ligne × 3) | dizaines de clés × 3, + lint i18n à construire |
| État réel aujourd'hui | 1 seule règle CSS RTL, 0 primitive dir-aware | — |

**Décision consignée au DONE LOG de `docs/PLAN2.md`.**
