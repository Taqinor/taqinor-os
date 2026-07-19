# BLUEPRINT — Refonte de la page LEADS (pipeline home) — Groupe LB
*Synthèse design (Fable), 2026-07-19. Sources : recon2/01-05 + recon/02+06, source vérifié
(LeadsPage.jsx, KanbanView.jsx, stages.js, rotting.js, useOptimisticSave.js, crmSlice.js,
index.css 7073-7085, apps/crm/services.py `_rang_funnel`/`_bulk_stage_allowed`).*

C'est la première page du matin de Reda et Meriem. Objectif : le board tient dans l'écran
(fini le « scroller tout en bas pour aller à droite »), la carte dit l'essentiel en 4 lignes,
la liste devient un vrai tableau épinglé, les KPI sont des filtres, l'URL est partageable,
et les classes de bugs recon-03 meurent **par construction** (invariants D6).

---

## D1 — STRUCTURE : shell borné view-aware, header+filtres épinglés partout

**Verdict.** On duplique le pattern maison `.lw-page` (index.css:7073-7085) pour `.lp-page`,
avec UNE nuance : le shell est borné pour TOUTES les vues (header + FilterBar + KPI + barres
restent épinglés — le cockpit ne défile jamais), mais le **scrolleur** change de propriétaire
selon la vue, piloté par un attribut `data-view` posé sur la racine (1 ligne de JSX :
`<div className="page lp-page" data-view={view}>`).

- **kanban / prevision** : la zone de vue ne scrolle pas ; `.kb-board` est le scrolleur
  horizontal (sa scrollbar vit donc TOUJOURS au bas du viewport — le fix fondateur), chaque
  `.kb-col-body` est le scrolleur vertical de sa colonne. Les en-têtes de colonnes sont épinglés
  par construction (hors du corps scrollant), pas par `position:sticky`.
- **liste** : `.lv-wrap` devient LE scrolleur unique deux axes (`overflow:auto`) — indispensable
  car un ancêtre `overflow-x:auto` casserait `position:sticky` vertical du `thead` ; avec un seul
  conteneur de scroll, sticky top ET sticky left fonctionnent tous les deux.
- **calendrier / graphique / carte** : `.lp-view-area` scrolle verticalement (défaut) — le
  comportement « page » actuel, mais avec header/filtres épinglés.

**Kanban échappe au cap `max-width:1200` : OUI**, et la page ENTIÈRE passe en pleine largeur
pour les 3 vues denses (kanban, prevision, liste) — un board full-bleed sous un header centré
1200px aurait l'air cassé ; Linear/Trello alignent toolbar et board. Calendrier/graphique/carte
gardent le cap 1200 (lisibilité).

### Contrat CSS exact (bloc append-only `.lp-*`/`.kb-*`/`.lv-*` d'index.css)

```css
/* LB2 — chaîne de hauteur (miroir du pattern .lw-page, LW13/LW25) */
.layout-content > .route-fade:has(> .lp-page) { height: 100%; }
.lp-page { display: flex; flex-direction: column; height: 100%; min-height: 0; }
/* toutes les rangées du shell sont fixes, seule la zone de vue s'étire */
.lp-page > :not(.lp-view-area) { flex: 0 0 auto; }
.lp-page > .lp-view-area {
  flex: 1 1 auto; min-height: 0;               /* remplace min-height:320 */
  display: flex; flex-direction: column;
  overflow: hidden auto;                        /* défaut : scrolleur vertical de la vue */
}
/* vues « planche » : la zone ne scrolle pas, le scroll vit plus bas */
.lp-page[data-view="kanban"] .lp-view-area,
.lp-page[data-view="prevision"] .lp-view-area,
.lp-page[data-view="liste"] .lp-view-area { overflow: hidden; }
/* pleine largeur pour les vues denses (le cap .page 1200 saute) */
.lp-page[data-view="kanban"],
.lp-page[data-view="prevision"],
.lp-page[data-view="liste"] { max-width: none; }

/* board : height:100% (inerte — % sur containing block auto) REMPLACÉ par flex */
.kb-board { flex: 1 1 auto; min-height: 0; overflow-x: auto; }
.kb-col { display: flex; flex-direction: column; min-height: 0; }
.kb-col-body { flex: 1 1 auto; min-height: 0; overflow-y: auto; }

/* liste : UN seul scrolleur deux axes, sticky top + left dedans */
.lv-wrap { flex: 1 1 auto; min-height: 0; overflow: auto; }
.lv-table thead th { position: sticky; top: 0; z-index: 2; background: var(--card); }
@media (min-width: 768px) {
  .lv-table .lv-sticky-name { position: sticky; left: 0; z-index: 1; background: var(--card); }
}

/* scrollbars fines TOUJOURS visibles (Linear/Notion) — tokens, deux thèmes */
.kb-board, .kb-col-body, .lv-wrap { scrollbar-width: thin; scrollbar-color: var(--border) transparent; }
.kb-board::-webkit-scrollbar { height: 10px; }
.kb-col-body::-webkit-scrollbar { width: 8px; }
.kb-board::-webkit-scrollbar-thumb, .kb-col-body::-webkit-scrollbar-thumb,
.lv-wrap::-webkit-scrollbar-thumb { background: var(--border); border-radius: 999px; }
```

**Gardes-fous.** (1) Ne PAS toucher la règle `:has(> .lw-page)` existante. (2) Les early-returns
StateBlock (chargement/erreur) rendent SANS `.lp-page` → croissance naturelle, aucun risque
(LB27 remet le squelette DANS le shell). (3) `ForecastView` rend `.kb-board.fv-board` → hérite
du contrat sans travail. (4) Mobile : le padding bas de `.layout-content` (tabbar) reste porteur ;
le board mobile garde ses colonnes 85vw MAIS avec scroll interne par colonne. (5) L'opacité
`isFiltersStale` inline sur `.lp-view-area` est compatible. (6) Le gap responsive 769-899px
(recon-05) se règle dans la même passe : `.kb-col` en `clamp(220px, 24vw, 272px)` entre 768 et 1024.

---

## D2 — ERGONOMIE DU BOARD

- **En-têtes de colonnes** : épinglés par construction (D1). Nouvelle mise en page : rangée 1
  titre + compteur (toujours visible, même à 0) ; rangée 2 `total MAD · Prév. pondéré`
  (masquée si total 0, comme aujourd'hui), tooltip expliquant la pondération
  (`STAGE_PROBABILITY`, déjà exporté de KanbanView et réutilisé par ForecastView — on n'en
  déclare JAMAIS une seconde table). Chaque colonne devient une région nommée
  (`<section aria-label="Étape Nouveau — 12 leads">`), chaque `.kb-col-body` reçoit
  `tabindex="0"` + `aria-label` (zone de scroll atteignable au clavier — recon-05 a11y #6).
- **autoScroll dnd-kit** : intégré à `DndContext` (activé par défaut) — il était inerte parce
  qu'AUCUN conteneur ne scrollait (D1 le réveille). Tâche = vérifier le comportement sur les deux
  axes imbriqués (board x, colonne y) et régler `autoScroll={{ thresholds: { x: 0.18, y: 0.22 } }}`
  si les défauts frottent. Config, pas de code maison (recherche #40).
- **Drag-to-pan sur l'espace vide** (Trello — ajouté pour exactement la plainte du fondateur) :
  hook `usePanScroll(boardRef)` (nouveau, `features/kanban/usePanScroll.js`) — `pointerdown`
  bouton 0 sur le board, IGNORE tout `e.target.closest('.kb-card, .kb-col-body, button, a, select,
  input, [role="button"]')` (aucun conflit avec le PointerSensor : ses listeners vivent sur les
  cartes), seuil 4px avant capture, `setPointerCapture`, curseur `grab/grabbing`, désactivé sur
  pointer coarse (le toucher scrolle nativement). Shift+molette : natif, gratuit dès D1 — zéro
  handler wheel maison.
- **Repli de colonne persisté** : chevron dans l'en-tête → colonne repliée = rail vertical 44px
  (libellé pivoté + compteur), qui RESTE une zone droppable (surbrillance à l'over, drop autorisé).
  Persistance `localStorage['taqinor.leads.kanban.collapsed']` (tableau de clés d'étape). Aucun
  repli par défaut — le choix appartient à l'utilisatrice.
- **COLD-réactivation (bug #7) — verdict : COLD se classe SOUS les étapes actives.** Le backend
  fait DÉJÀ exactement ça (`services._rang_funnel('COLD') == -1` ; `_bulk_stage_allowed` :
  Froid → active = réactivation autorisée, → Froid = parking autorisé depuis partout, sinon
  avant-seulement). Le bug est 100 % client : `stageRank = PIPELINE_STAGES.indexOf` classe COLD
  au rang 5 (le plus HAUT) → tout drag COLD→actif est bloqué comme « recul ». Fix : ajouter à
  `stages.js` `funnelRank(stage)` (COLD → -1) et `isStageMoveAllowed(from, to)` — miroir
  byte-à-byte de `_bulk_stage_allowed` — et l'utiliser dans le garde du drag, dans les `<option>`
  du StageMover (options interdites `disabled`) et dans l'InlineEdit stage de la liste (le chemin
  clavier retrouve le MÊME garde que le drag — bug #8 meurt aussi). SIGNED reste gardé : y entrer
  passe par SigneDialog quel que soit le chemin ; en sortir en arrière reste interdit (sauf → Froid,
  comme le serveur). **Aucune tâche backend.**
- **Parité clavier + restauration du focus** : KeyboardSensor + annonces FR existent. Après un
  drop (souris OU clavier), la carte se re-parente → focus perdu sur `<body>` (recon-05 a11y #4).
  Fix : `data-lead-id` sur le nœud draggable ; à `onDragEnd` réussi, `requestAnimationFrame` →
  `querySelector('[data-lead-id="N"]')?.focus()`.

---

## D3 — LA CARTE : 4 zones, plafonnée, qui dit « quoi faire ensuite »

Hiérarchie **nom → valeur → prochaine action → âge**. Contrat DOM conservé :
`article.kb-card` + `.kb-card-name` (e2e).

```
┌─────────────────────────────────────────┐
│ [✓] Nom du lead            ⛁92  [•••]  │  tête : check (hover/sélection), nom, ScoreBadge, menu
│ 45 000 MAD · Résidentiel                │  valeur : montant (devis sinon estimé) + type chip
│ ⚠ Relance en retard — 12 jul            │  UNE ligne d'action : pill d'alerte OU prochaine action
│ Meta · Casablanca   ▪12 j   (RK)        │  pied : canal·ville · pill d'âge (rotting) · avatar
└─────────────────────────────────────────┘
```

- **Tête.** Checkbox : rendue en permanence mais `opacity:0` → visible au `:hover`,
  `:focus-within`, quand une sélection est active (prop `selectionActive`), et TOUJOURS sur
  `(hover: none)` ; zone de frappe ≥44×44 via padding (tue le sliver 16px, recon-05 touch).
  ScoreBadge conservé tel quel (tooltip top-3 raisons, test pinné). Menu `•••` (DropdownMenu)
  révélé hover/focus, permanent au toucher : Ouvrir · Planifier une relance · ⚡ Devis auto ·
  ✗ Marquer perdu · Archiver. Le bouton ✗ quitte la face (son popover 20×20 intouchable meurt).
- **Valeur.** `latestDevisTotal` sinon `montant_estime` (préfixe « est. ») ; chip type
  d'installation. Rien d'autre.
- **Prochaine action — UNE seule ligne**, précédence : pill perdu > relance en retard >
  ☎ rappel demandé > devis expiré > `next_activity` > suggestion existante (logique VX24
  conservée, juste re-logée). Sur une carte NEW non contactée, cette ligne EST le badge SLA
  premier-contact (le timer QX31 fusionne ici : « À contacter — 2 h » ambre/rouge).
- **Pied.** Canal + ville · **pill d'âge « rotting »** · AssigneePicker avatar. Étoiles priorité :
  déjà encodées dans le tri de colonne + éditables via la fiche — quittent la face (bruit).
- **Rotting (réutilise `workspace/rotting.js` TEL QUEL)** : `stage_since_days` est dans le
  payload ; `rottingLevel(days, thresholdsForIndex(PIPELINE_STAGES.indexOf(stage)))` →
  `data-rot="ok|warning|danger"` sur la carte. Style : pill d'âge teintée (neutre/ambre/rouge,
  tokens `--warning`/`--destructive`), + liseré intérieur gauche 3px UNIQUEMENT en danger
  (discret, pas un sapin de Noël). Jamais de rot sur SIGNED/COLD (seuils null) ni sur perdu.
- **Ce qui QUITTE la face** (recherche #19 : titre + peu de propriétés, le détail vit dans la
  fiche) : liens tel/WhatsApp toujours visibles → **actions rapides révélées au hover** (pied,
  permanentes sur `(hover:none)`) — le réflexe d'appel de Meriem survit, la carte respire ;
  chips readiness 📍🧾⚡ → micro-icônes 12px tooltipées dans le pied (plus de styles inline) ;
  tags plafonnés à 2 + « +N » ; « Inactif N j » + horloge → absorbés par la pill d'âge ;
  bouton ⚡ pleine-face → menu ••• ET action rapide hover.
- **Tags TOKENISÉS** : `TAG_PALETTE`/`TAG_TEXT` (20 hex, stages.js:85-91) remplacés par 10 paires
  de tokens `--tag-1-bg/--tag-1-fg … --tag-10-bg/--tag-10-fg` définies clair + sombre dans
  `design/tokens.css` ; `tagColor()` garde sa signature et renvoie `var(--tag-N-…)` (LeadCard et
  ListView en profitent sans changement). Le hash déterministe est conservé.
- **Bug WhatsApp-bleu** : le fond du swipe utilise `var(--color-info, #25D366)` et `--color-info`
  EXISTE (bleu). Nouveau token de marque `--brand-whatsapp` (vert WhatsApp, clair+sombre, défini
  dans tokens.css — le SEUL endroit où un hex a le droit de naître) ; les 3 fallbacks morts
  `--color-*-muted` de LeadCard/`.kb-call-nudge`/`.lv-call-nudge` sont re-basés sur des tokens réels.
- **PII masquée visible** : quand l'utilisateur n'a pas la permission PII (le serializer nullifie
  tel/email/adresse/whatsapp/gps), les actions d'appel sont remplacées par un cadenas 12px
  tooltipé « Coordonnées masquées (permission PII) » — plus jamais un blanc inexplicable.
- **Mobile** : swipe ☎/💬 conservé (bande cachée passe en `inert` — l'aria-hidden actuel laisse
  les `<a>` tabbables) ; menu ••• permanent ; checkbox permanente quand sélection active.

---

## D4 — LISTE : REFIT SUR PLACE (pas d'adoption du moteur ui/datatable) — l'appel le plus risqué

**Verdict : refit en place, en volant 2 pièces du moteur (`useColumnPrefs` + `ColumnManager`).**

Pourquoi pas l'adoption complète, pesée honnêtement :
1. **« Un seul état de filtre partout » (D5) est un invariant.** Le moteur apporte son propre
   FilterBuilder + `urlState` : brancher DataTable sur la page leads créerait un SECOND modèle de
   filtres et un SECOND écrivain d'URL sur une page qui partage déjà UN état entre 6 vues. C'est
   une contradiction architecturale, pas un détail.
2. **Le contrat e2e/tests pinne le DOM actuel** (`tr.lv-row`, `.lv-lead-name`, `.ie-cell`,
   `select.ie-input`, hrefs tel/wa + stopPropagation, « Plus d'actions sur la ligne »). Shimmer
   ces classes dans le DOM d'un moteur étranger ([data-dt-*]) = théâtre de contrat avec un vrai
   risque de régression sur specs CI-gated.
3. **~70 % des 753 lignes sont des cellules métier lead** (liens call-ready, perdu, Parcours,
   ⚡ devis auto, archived-by, badges) qui seraient réécrites en cellules custom de toute façon.
   L'adoption n'achète réellement que ColumnManager + sticky — qu'on peut voler à l'unité.
4. **Asymétrie de risque.** Le refit est incrémental (4 tâches, chacune committable/révertable) ;
   l'adoption est un big-bang sur la page la plus utilisée de l'ERP, avec la barre bulk du moteur
   à réconcilier contre la barre bulk serveur (`bulkLeads`) existante.

Ce qu'on vole au moteur (imports directs, zéro fork) : **`useColumnPrefs`** (visibilité de
colonnes persistée, clé `taqinor.leads.columns`) + **`ColumnManager`** (UI de choix de colonnes),
alimentés par un modèle de colonnes déclaré en tableau dans ListView. `FilterBuilder`,
`urlState`, `DataTable`, la bulk-bar du moteur : explicitement NON.

Le refit livre : scrolleur unique + `thead` sticky + colonne nom sticky-left ≥768 (D1),
`<colgroup>` à largeurs fixes (l'édition inline ne fait plus danser les colonnes — P3 #14),
choix de colonnes persisté, option « Par étape » (rangées de groupe collantes sous le thead :
StatusPill étape + compteur + total MAD, repliables, persisté), lignes ouvrables au clavier
(Enter/Espace sur `tr` focusable + le nom en vrai lien), adoption du `PerduPopover` partagé
(fin de la duplication byte-à-byte carte/liste), stabilité mémo des lignes (l'état du popover
perdu sort des props de CHAQUE ligne : une seule instance au niveau table, les lignes ne
reçoivent que des booléens + callbacks stables). Mobile <768 : card-stack global conservé,
sticky-left désactivé.

---

## D5 — PAGE : KPI-filtres, URL partageable, bulk flottant

- **Bandeau KPI sur le SHELL** (nouvelle rangée entre header et FilterBar, `LeadsKpiStrip.jsx`),
  compact (36px, scroll-x sur mobile), 4 tuiles :
  1. **Dû aujourd'hui** → toggle `relance='aujourdhui'` (NOUVELLE valeur de `filterLeads` :
     `relance_date === today`) ;
  2. **En retard** → toggle `relance='retard'` (existant) ;
  3. **Chauds** → toggle `score='chaud'` (NOUVELLE clé de filtre sur `score_label`) ;
  4. **Pipeline** (affichage seul, jamais un filtre) : `Σ latestDevisTotal` des leads filtrés non
     perdus + « pondéré » via `STAGE_PROBABILITY` — les MÊMES nombres que les colonnes (règle
     Pipedrive #31 : tous les totaux lisent le même état filtré).
  Tuiles 1-3 = `<button aria-pressed>` ; **compte facetté** : le compte d'une tuile = taille de
  `filterLeads(leads, { …filtresActifs, saPropreDimension: appliquée })` — cliquer donne
  exactement ce que le chiffre promet. Actives = accent `--module-accent-azur`.
- **Un seul état de filtres partout** : KPI, FilterBar, colonnes, vues, export lisent tous
  `filters` de LeadsPage. Aucun état de filtre local dans aucune vue. (Invariant D6-I7.)
- **URL partageable** : nouveau module pur `pages/crm/leads/urlFilters.js`
  (encode/decode `filters+view ↔ URLSearchParams`, n'écrit QUE les clés non-défaut, préserve
  `lead`/`new`/`equipe`, testable node). Priorité au chargement : **URL > localStorage > défauts**
  (une URL collée gagne toujours) ; écriture débouncée 300ms en `replace` (jamais de spam
  d'historique) ; `?view=` devient enfin un lien profond. `applySavedView` écrit l'URL.
- **FilterBar** : recherche débouncée 250ms (état local input → `setFilters`), `useDeferredValue`
  conservé en 2e étage ; chips actives inchangées ; Segmented relance gagne « Aujourd'hui ».
- **Vues enregistrées** : shape actuelle conservée ; chaque chip gagne « Copier le lien »
  (sérialise via urlFilters — le partage Reda→Meriem devient un collage WhatsApp).
- **Bulk flottant** : la barre inline (qui pousse le layout à chaque sélection) devient une
  toolbar flottante bas-centre (`position:fixed`, `z-index:var(--z-sticky)`, safe-area + au-dessus
  de la tabbar mobile, slide-in-up `--motion-base`, honore reduced-motion). MÊME composant
  BulkActionBar (toutes les actions conservées), nouveau wrapper `.lp-bulk-float`.
- **Empty states coach** : global 0 lead → CTA « + Nouveau lead » / « Importer » ; 0 résultat
  filtré → « Effacer les filtres » (CTA réel) ; colonne vide → zone de drop en pointillés
  « Déposer un lead ici » ; ForecastView reçoit ENFIN un EmptyState (gap connu).
- **Express/FAB** : FAB mobile inchangé (openNew — le texte e2e « + Nouveau lead » et VX42 ne
  bougent pas) ; le bouton Express rejoint le menu ⋯ sous 768px (le header respire).
- **Insights : PAS de relocalisation.** Les 3 fetches de CrmInsightsPanel n'ont rien à faire dans
  le chargement du matin ; le panneau reste dans ChartsView (la vue d'analyse), avec un cache
  session 60s pour ne plus re-fetcher à chaque bascule de vue. L'essence « SLA » vit déjà sur
  les cartes NEW (badge premier-contact D3).

---

## D6 — MODÈLE D'ÉTAT/PERF : les invariants qui tuent les bugs par construction

Le fetch-all reste (volumes réels : quelques centaines de leads ; le kanban veut tout voir) —
mais le refetch intégral par micro-édition meurt. **Pas de virtualisation ce tour** (d'accord
avec la recherche : mesurer d'abord ; colonnes bornées = coût de peinture réduit ; seuil de
ré-examen : >~1 000 leads ou jank mesuré).

**I1 — Un PATCH mono-lead ne refetch JAMAIS.** `updateLead.fulfilled` remplace déjà le lead dans
le store avec le payload serveur complet (score recalculé, stage_since_days, devis…). `onInlineSave`
perd son `.then(refetch)` ; `reassign` perd son `refetch()`. Le refetch intégral n'est légitime
qu'après : bulk, import, merge, SigneDialog confirmé, création (express/form), changement du
filtre serveur `archived`.
**I2 — Toute mutation passe par le store.** Plus AUCUN `crmApi.updateLead` direct dans une
carte/ligne : « perdu » remonte via un callback stable `onMarkPerdu(lead, motif)` de LeadsPage
(dispatch `updateLead({perdu:true, motif_perte})`) — la carte se met à jour par le store (bug #3
mort). La prop fantôme `onChanged` et les commentaires « polling » mensongers sont supprimés.
Archiver/restaurer en liste passent par les thunks `archiveLead`/`restoreLead` (déjà réduits).
**I3 — L'interception « Signé » est honnête.** `onInlineSave(lead,'stage', SIGNED)` ouvre
SigneDialog et renvoie `Promise.reject(SIGNE_INTERCEPT)` (sentinelle exportée d'un module
`pages/crm/leads/signeIntercept.js`) : `useOptimisticSave` fait son rollback (le select REVIENT à
l'étape réelle — fini le « Signé ✓ Enregistré » fantôme, bug #2), et l'`onError` du StageMover
avale la sentinelle sans toast (`isSigneIntercept(err)`). InlineEdit (liste) restaure déjà par
rejet — même contrat, zéro cas spécial.
**I4 — Stabilité mémo totale.** TOUS les callbacks de `viewProps` sont `useCallback` ;
`viewProps` est `useMemo` ; `DraggableCard` est mémoïsé ; les lignes de liste ne reçoivent que
des primitives/refs stables (l'état du popover perdu vit au niveau table). Corollaire mesurable :
une frappe dans la recherche ne re-rend AUCUNE carte (test de sonde léger).
**I5 — La sélection est élaguée contre `filtered`**, plus contre `leads` : un lead masqué par un
filtre ne peut PAS être bulk-acté (bug #6). La barre flottante affiche le compte visible.
**I6 — Les refetch sont gardés contre l'obsolescence.** `crmSlice` trace le `requestId` du
dernier `fetchLeads` ; un `fulfilled` obsolète est ignoré (fin du flicker revert post-drag,
bug #10) — même motif que `leadUpdateSeq` existant.
**I7 — Un seul état de filtres, une seule écriture d'URL** (cf. D5) ; recherche débouncée
250ms + URL débouncée 300ms.
**I8 — Aucune erreur silencieuse.** `reassign`, exports, archive/restore, perdu : chaque échec
produit un `toastError` FR (bug #11).
**I9 — Squelette dans le shell.** Premier chargement : squelette EN FORME de la vue active
(6 colonnes × 3 SkeletonCard, ou rangées de table) via `useDelayedLoading`+`FadeSwap`, DANS le
shell borné (header visible immédiatement). Erreur : StateBlock inchangé.

---

## CARTE DES FICHIERS (lanes file-disjointes après LANE 0)

**LANE 0 (urgence, séquentielle, propriétaire des fichiers cœur) :**
`frontend/src/index.css` (bloc LB append-only), `frontend/src/pages/crm/leads/LeadsPage.jsx`,
`frontend/src/pages/crm/leads/views/KanbanView.jsx`, `frontend/src/pages/crm/leads/views/ListView.jsx`,
`frontend/src/pages/crm/leads/views/LeadCard.jsx` (retouches ≤ petites), `frontend/src/features/crm/stages.js`
(funnelRank), `frontend/src/features/crm/store/crmSlice.js` (seq guard),
NOUVEAU `frontend/src/pages/crm/leads/signeIntercept.js`.
**LANE A (board)** : `views/KanbanView.jsx`, NOUVEAU `features/kanban/usePanScroll.js` (+ test),
index.css `.kb-*`.
**LANE B (carte)** : `views/LeadCard.jsx`, NOUVEAU `pages/crm/leads/PerduPopover.jsx`,
`design/tokens.css`, `features/crm/stages.js` (tagColor SEULEMENT), index.css `.kb-card*`.
**LANE C (liste)** : `views/ListView.jsx`, index.css `.lv-*` (+ imports ui/datatable/useColumnPrefs,
ColumnManager — lecture seule du moteur).
**LANE D (shell/filtres/KPI/URL)** : `LeadsPage.jsx`, `FilterBar.jsx`, `BulkActionBar.jsx`,
`components/SavedViewsBar.jsx` (prop additive), NOUVEAUX `pages/crm/leads/LeadsKpiStrip.jsx`,
`pages/crm/leads/urlFilters.js` (+ test node), `features/crm/stages.js` (filtres — @after lane B),
index.css `.lp-*`.
**LANE E (vues secondaires)** : `views/ForecastView.jsx`, `views/CalendarView.jsx`,
`views/CarteView.jsx`, `views/ChartsView.jsx`, `components/CrmInsightsPanel.jsx`, index.css.
**LANE F (polish/dark)** : index.css seul (hex kill), puis sweep `useIsMobile`/ViewSwitcher
(@after lanes C/D/E).
**LANE G (tests/e2e/goldens)** : `e2e/tests/leads-board.spec.js` (nouveau), goldens
`leads-kanban` light+dark, passe axe.

Conflits résiduels assumés : `stages.js` (B puis D via @after) ; `LeadsPage.jsx` (lane 0 puis D) ;
`index.css` append-only (exempt par la règle plan_lanes).

---

## TRAITEMENTS PAR VUE (résumé)

- **Kanban** : board borné full-bleed, colonnes scrollables, headers riches épinglés, repli
  persisté, pan + autoscroll + shift+molette, cartes D3, COLD réactivable, focus restauré.
- **Prévision** : hérite du shell borné et du contrat `.kb-board` ; parité clavier (sensor +
  `<select>` mois par carte + annonces), busy-lock réel via `busyLeadId`, listeners isolés sur
  poignée, EmptyState global + hints de drop ; totaux pondérés inchangés (même STAGE_PROBABILITY).
- **Liste** : refit D4 (sticky ×2, colgroup, chooser, groupes par étape, clavier, PerduPopover).
- **Calendrier** : chips aux tons d'étape tokenisés, aujourd'hui cerclé, retard souligné
  destructive ; double-post relance+visite CONSERVÉ (c'est une feature, deux échéances réelles).
- **Carte** : `hoveredId` mort → câblé (survol liste sans-GPS ⇒ pin mis en avant) ; popup Leaflet
  re-basée tokens via CSS ; split avec/sans GPS conservé.
- **Graphique** : inchangé structurellement ; insights cache session 60s ; empty coach.

---

## STRATÉGIE E2E / GOLDENS / A11Y

- **Sélecteurs pinnés conservés à l'identique** : `article.kb-card`, `.kb-card-name`, `tr.lv-row`,
  `.lv-lead-name`, `.ie-cell`, `select.ie-input`, libellés 'Vue kanban'/'Vue liste', les 6 libellés
  d'étape, '+ Nouveau lead', '✓ Enregistré', « Plus d'actions sur la ligne », 'Passer en « Signé »'.
  Chaque tâche qui touche un hook pinné le met à jour DANS la même tâche.
- **Goldens** `leads-kanban` light+dark (release-verify) : CHANGENT forcément → régénération
  délibérée en fin de batch (LB34), jamais un red release-verify surprise.
- **Axe (VX71, CI-gated)** : chaque nouveau contrôle est nommé (tuiles KPI `aria-pressed`,
  chevrons de repli labellisés, zones de scroll `tabindex=0`+label, menu ••• labellisé) ; la
  structure draggable actuelle (qui passe axe aujourd'hui) n'est PAS restructurée.
- **Nouveau spec de régression** `leads-board.spec.js` : en vue kanban le shell ne scrolle pas
  (scrollHeight ≈ clientHeight du scrolleur parent), la scrollbar horizontale du board est dans
  le viewport, un `.kb-col-body` scrolle ; en liste le `thead` reste visible après scroll.
- **Tests unitaires pinnés** (VX24, first-touch, ReadinessChips, SwipeAction, KanbanView.test,
  ListViewCallReady, ForecastView…) : mis à jour dans la tâche qui change le comportement,
  jamais en sweep différé.
