# BLUEPRINT — Lead Workspace (« la plus belle fenêtre de l'ERP »)

Synthèse de design, 2026-07-18. Référence UNIQUE pour tous les agents de build du Groupe LW.
Fondé sur les 7 rapports recon (`scratchpad/recon/01..07`) + lecture directe de
`frontend/src/pages/crm/LeadForm.jsx` (2057 l.), `ui/ResponsiveDialog.jsx`, `docs/PLAN2.md`.

---

## D1 — ARCHITECTURE : (c) UN composant `LeadWorkspace`, deux enveloppes — CONFIRMÉ

**Verdict : (c).** Un seul composant `LeadWorkspace` rendu :
1. **Depuis la liste/kanban** (`LeadsPage.jsx`) : Dialog quasi-plein-écran
   (`w-[min(1440px,96vw)] h-[min(920px,94dvh)]`), conservant le contrat existant
   `lead / leadsQueue / onNavigateLead / onClose / onSaved` — la rafale J/K et ◀▶ (VX224)
   survit intégralement, LeadsPage reste seule propriétaire de `editLead` et de la file filtrée.
2. **En pleine page** à `/crm/leads/:id` (`LeadDetailPage.jsx`) : même composant, `variant="page"`,
   même grille interne, sans overlay. La page gagne ENFIN J/K (aujourd'hui absent sur cette route —
   recon 01 §1) via une file reconstruite optionnelle (non bloquant, la page marche sans file).

**Pourquoi pas (a)** — un modal élargi garde le confinement psychologique ET l'anatomie plate
fragile (les enfants du grid Radix sont des frères plats, recon 04 §3 : c'est exactement la
construction qui a produit le bug P0). **Pourquoi pas (b)** — la pleine page seule casserait le
flux « ouvrir/fermer 30 fiches au-dessus de la liste filtrée » qui est LE geste quotidien de
Reda/Meriem ; déplacer la file dans l'URL/store est un chantier sans gain utilisateur.
**(c) coûte ~40 lignes de shell de plus** que (a) et unifie deux chemins aujourd'hui divergents
(la route détail n'a ni file ni J/K). C'est le choix Linear (record = composant, enveloppe = contexte).

Implémentation shell :
- `variant="dialog"` : `Dialog`/`DialogContent` (≥768px) avec une nouvelle classe de taille
  `lw-dialog` ; `<768px` : `Sheet side="bottom"` pleine hauteur (`h-[100dvh]`). On n'utilise PAS
  `ResponsiveDialog` tel quel (son body partagé rend l'en-tête/pied génériques) — on compose
  directement `Dialog`+`Sheet` comme lui, dans `LeadWorkspace.jsx`.
- `variant="page"` : `<div className="lw-root lw-page">`, même grille.
- **Le scroll est correct PAR CONSTRUCTION** : la racine interne est `display:grid;
  grid-template-rows: auto 1fr; grid-template-columns: [rails]` avec `min-height:0` sur la
  rangée 1fr ; CHAQUE zone (centre, rail droit) est son propre conteneur `overflow-y:auto`.
  Plus jamais un `<form>` sans classe entre le grid et le corps scrollable (cause racine P0,
  recon 04 §3). Le `<form>` n'existe qu'en mode création et porte explicitement
  `className="lw-form"` avec `display:contents`.

---

## D2 — MODÈLE D'ÉDITION : HYBRIDE — champs toujours-éditables + autosauvegarde par vidage de « draft », création reste un formulaire rapide

**Verdict : hybride, PAS du click-to-edit Attio.** Reda/Meriem TAPENT dans cette fenêtre toute la
journée : des inputs toujours visibles et toujours éditables (comme aujourd'hui) battent le
click-to-edit (un clic de plus par champ, focus fragile). Ce qui change : **en édition, plus de
bouton « Mettre à jour » obligatoire** — les modifications se sauvegardent seules (blur + debounce
1,5 s), avec un état visible. Un bouton « Enregistrer » subsiste dans le bandeau (flush manuel +
compat e2e + réassurance). **En création : formulaire classique inchangé** (un submit, défauts
VX93, « créer un autre » VX224/92 intact) — la rafale de création ne doit jamais payer
l'autosauvegarde.

### Le moteur d'état : `useLeadDraft` — la spec qui rend la perte de données IMPOSSIBLE

Un seul hook possède TOUT l'état mutable par-lead. Réducteur pur dans `draftCore.js`
(testable en node --test), hook React dans `useLeadDraft.js`.

```
state = {
  leadId,                     // la CLÉ. Tout l'état ci-dessous meurt avec elle.
  server,                     // dernière vérité serveur (successeur de liveLead)
  draft,                      // SPARSE : { champ: valeur } — UNIQUEMENT les clés touchées
  inflight,                   // { champ: valeur } envoyées, en attente de réponse | null
  saveState,                  // 'idle' | 'saving' | 'saved' | 'error'
  saveError,                  // message | null
  stale,                      // { theirs, at } | null  (garde VX243c, portée par leadId)
  composer: { note, file },   // brouillon de note chatter
  wa: { selected:Set, langue, preview },
  bill: { editing, hiver, ete, error },
}
```

**Actions (sémantique contractuelle — chaque règle tue une classe de bug recon 05) :**

1. `LOAD_LEAD(lead)` — remplacement ATOMIQUE de l'état entier. Il n'existe AUCUN état satellite
   hors du store keyé : la navigation J/K/◀▶ ne peut structurellement plus transporter
   `waSelected` (P1#2), la note du composer (P1#4), l'édition facture (P2#8) ni la bannière
   stale (P2#7) d'un lead à l'autre.
2. `SET_FIELD(k, v)` — `draft[k] = v` ; si `canonEq(v, server[k])` → `delete draft[k]`.
   `dirty = Object.keys(draft).length > 0`. Fini le `JSON.stringify` de ~50 clés à chaque rendu
   (smell recon 01 §6.6) et fini le « phantom dirty » numérique (canonEq compare '' ≡ null,
   Number(x) ≡ Number(y)).
3. `FLUSH(keys = toutes les clés dirty)` — `inflight = slice(draft, keys)` ; PATCH partiel.
   - **Succès** : si `res.id !== state.leadId` → RÉPONSE JETÉE (garde de navigation — tue la
     course refreshLead/quickChangeStage, recon 01 §6.3). Sinon `server = res` ; pour chaque clé
     envoyée : `if (draft[k] === inflight[k]) delete draft[k]` — une frappe DURANT le vol reste
     dirty et repart au prochain flush (« typed-during-flight guard »). Les valeurs canonisées
     serveur (téléphones → 212XXXXXXXXX) sont ré-hydratées depuis `server`, jamais depuis
     l'optimiste.
   - **Échec** : `inflight` retourne dans `draft` (RIEN n'est perdu), `saveState='error'`,
     bandeau « Échec d'enregistrement — Réessayer », erreurs de champ via `useServerFieldErrors`.
4. **`stage` n'entre JAMAIS dans `draft`.** Le changement d'étape est une ACTION du
   `StageControl` : `flush()` d'abord, puis PATCH `{stage}` dédié — SIGNED intercepté par
   SigneDialog (couches funnel/document séparées, règles #2/#4), recul de funnel = 400 serveur
   affiché en toast explicatif. Le succès met à jour `server.stage` seulement — il ne touche pas
   `draft`, donc ne peut plus « blanchir » des éditions non sauvées (tue P1#1).
5. `leaveGuard(action)` — TOUTES les sorties (✕, overlay, Escape, J/K, ◀▶, archiver, convertir,
   navigation) passent par lui : si dirty → `FLUSH` d'abord, puis `action()` ; si le flush
   échoue → ConfirmDialog (ui/confirm) « Réessayer / Quitter en abandonnant ». L'archivage ne
   peut structurellement plus jeter des éditions (tue P1#3). En mode création, leaveGuard
   retombe sur `confirmLeaveIfDirty` (on ne crée pas un lead à moitié saisi en douce).
6. **Miroir sessionStorage** `taqinor.lead.draft.<id>` : `draft` (et `composer.note`) y est
   recopié à chaque changement, purgé au flush réussi. `LOAD_LEAD` restaure un brouillon
   orphelin avec un chip « Brouillon restauré ». Même un crash d'onglet ne perd plus une frappe.
7. **PII** : le backend expose `pii_masked` (booléen calculé, lane backend). Si vrai, les champs
   PII (telephone/email/adresse/whatsapp/gps) sont rendus read-only avec cadenas — le moteur ne
   les met jamais dans `draft`, donc jamais de « drop silencieux » côté PATCH.
8. **Garde stale (VX243c)** : conservée, déclenchée au premier FLUSH qui suit un
   `date_modification` externe ; la bannière et « Enregistrer quand même » vivent dans le state
   keyé → portée au bon lead par construction.
9. Coût serveur : chaque FLUSH = 1 PATCH = la chaîne 4-UPDATE existante — assumé et validé à
   l'échelle 2 utilisateurs (recon 02 §6) ; le debounce 1,5 s + flush-par-blur borne la
   fréquence à ~1 PATCH par champ quitté, pas par frappe.

**Feedback visuel** : chip d'état global dans le bandeau (`Enregistrement… / ✓ Enregistré /
⚠ Non enregistré — Réessayer`) + `FieldSavedPulse` (ui/) sur le champ qui vient d'être confirmé.
Jamais de spinner bloquant.

---

## D3 — LAYOUT : cockpit 3 zones adapté au solaire

### Desktop ≥1024px — grille `auto 1fr` / colonnes `288px minmax(0,1fr) 384px`

```
┌─ bandeau (auto) ─────────────────────────────────────────────────────────────┐
│ ◀ 3/41 ▶ · « Lead — Karim B. » (DialogTitle, compat e2e) · chip save-state · │
│ bannière stale (si conflit) · ✕                                              │
├─ rail identité 288px ──┬─ centre (scroll) ─────────┬─ rail contexte 384px ───┤
│ Avatar + Nom + société │ nav sections (chips       │ Tabs: Historique* │
│ + ville                │ horizontaux sticky,       │ Devis(N) │ Activités(N) │
│ StatusPill étape +     │ scroll-spy)               │ │ Pièces                │
│ « depuis N j » teinté  │                           │                         │
│ rotting                │ ▸ Suivi commercial        │ [Historique]            │
│ ScoreBadge (+ popover  │ ▸ Contact & site          │  1er/dernier contact ·  │
│ score_reasons)         │ ▸ Profil énergétique      │  N touches (points-     │
│ Triade OBLIGATOIRE :   │ ▸ Pompage (agricole)      │  contact)               │
│  Responsable ·         │ ▸ Toiture                 │  filtre par type ·      │
│  Prochaine action ·    │ ▸ Visite technique        │  note épinglée en tête  │
│  Relance (édit rapide) │   (AppointmentBooker)     │  ChatterTimeline        │
│ Chips préparation      │ ▸ Origine web (replié,    │  composer (note+fichier │
│ 📍🧾⚡ (QX28)           │   DefinitionList)         │  +CallLogPopover)       │
│ Bannières : doublons(N)│ ▸ Champs personnalisés    │ [Devis]                 │
│ · client_match ·       │ ▸ Note générale           │  CTA Devis auto (ou     │
│ carte-collée           │                           │  champs manquants       │
│ Actions : WhatsApp ·   │                           │  cliquables devis_auto) │
│ Appeler · Devis auto · │                           │  cartes devis (Status-  │
│ Toiture 3D 📍 ·        │                           │  Pill, total .num,      │
│ Convertir · Archiver   │                           │  facture/chantier)      │
│                        │                           │  barre WhatsApp FR/     │
│                        │                           │  Darija + aperçu        │
└────────────────────────┴───────────────────────────┴─────────────────────────┘
```

**Rail identité (gauche, 288px, scroll propre si déborde)** — tout ce qu'on regarde AVANT
d'appeler : identité, étape + ancienneté d'étape (`stage_since_days` avec rampe « rotting » :
NEW >2 j ambre / >5 j rouge ; CONTACTED & QUOTE_SUIVI >7/14 ; FOLLOW_UP >14/30 — teintes
`--warning`/`--destructive` à 12 % de fond), score AVEC ses raisons (popover `score_reasons`,
enfin surfacé), la triade responsable/prochaine action/relance (édition rapide sur place),
chips de préparation, bannières contextuelles (doublons → dialog de fusion ; client_match →
« Déjà client ? » + lien ; carte de visite collée → « Répartir »), pile d'actions. Le bouton
WhatsApp et « Devis auto » sont les 2 CTA visuellement premiers.

**Centre** — LE formulaire de qualification, en scroll unique avec nav-chips sticky
(scroll-spy conservé, throttlé rAF, `aria-current`). Sections = `Card` repliables (état plié
persisté par section, `localStorage`). « Origine web » toujours replié par défaut
(DefinitionList read-only). Devis/Activités/Pièces/Doublons/Historique QUITTENT le centre
(→ rail droit / bannières) : le centre ne contient QUE ce qui se saisit. La saisie facture
inline (lead-subbar actuel) devient le champ normal de la section Énergie — l'autosauvegarde
rend le raccourci redondant.

**Rail contexte (droit, 384px)** — `ui/Tabs` : **Historique** (défaut ; en-tête compact
« 1er contact / dernier contact / N touches » depuis `points-contact/`, filtre par type
persisté, notes épinglées en tête (backend `pinned`), ChatterTimeline + composer + fichier +
CallLogPopover), **Devis (N)** (chaîne document : cartes devis avec StatusPill statut devis —
JAMAIS DocumentStageTrack pour le funnel lead, mais OK pour la chaîne devis→facture→chantier
d'UNE carte —, actions générer facture / créer chantier, CTA « Devis automatique » qui liste
les champs manquants de `devis_auto` en LIENS qui sautent au champ du centre, barre d'envoi
WhatsApp multi-devis FR/Darija + aperçu serveur), **Activités (N)** (ActivitiesPanel +
« Appliquer un plan »), **Pièces** (AttachmentsPanel). Badges de compte sur les onglets.

**Au-dessus de la ligne de flottaison** : bandeau + rail identité entier + 1re section du
centre + l'onglet Historique. **Replié** : Origine web, sections cochées repliées. **Onglet vs
scroll** : tout ce qui se SAISIT scrolle au centre ; tout ce qui se CONSULTE s'onglete à droite.

### 768–1024px
Grille 2 colonnes : rail identité 240px + centre ; le rail contexte devient un 4e/5e… onglet
DANS la nav du centre ? Non — il glisse sous forme de `Sheet side="right"` togglable par un
bouton « Contexte » du bandeau (patron LeadDevisPanel existant). Le bug de bande 721-767px
(recon 04 §5) disparaît : le breakpoint UNIQUE est 768 (mêmes 767px partout).

### Mobile <768px — Sheet bas pleine hauteur
Ordre vertical : bande identité compacte (avatar, nom, StatusPill, score) → barre d'actions
POUCE (sticky bas, safe-area : Appeler · WhatsApp · Note) → triade → sections en accordéon →
onglets contexte. `FormActions` sticky pour le mode création. Le clavier iOS reste géré
(useKeyboardAwareScroll sur le conteneur scrollable du centre).

### Ce qui est CONSERVÉ à l'identique (affordances métier — rien n'est droppé)
WhatsApp FR/Darija + aperçu + garde téléphone ; Devis auto + menu (remise/onepage/premium/
édition) + LeadDevisPanel ; « Concevoir la toiture (3D) » 📍 ; Convertir en client (ZSAL4) ;
Archiver/Restaurer ; fusion doublons ; AppointmentBooker ; « Appliquer un plan » (ZSAL2) ;
champs personnalisés ; carte-collée VX237 ; bannières doublons live VX239 ; score ; chips
QX28 ; garde stale VX243c ; créer-un-autre VX224 ; défauts VX93 + « suggéré » VX249b ;
raccourcis 1-4/a/d + J/K ; SigneDialog + DealSignedCelebration.

### Richesses backend enfin surfacées
`score_reasons` → popover du ScoreBadge (rail identité). `devis_auto.missing/message` → CTA de
l'onglet Devis avec liens-sauts. `stage_since_days` → rotting sous la StatusPill.
`client_match/` → bannière rail identité. `points-contact/` → en-tête de l'onglet Historique.
`pinned` (nouveau) → épingle chatter.

---

## D4 — LANGAGE VISUEL (règles concrètes, tokens nommés)

1. **Discipline d'accent** : les surfaces sont neutres (`--card`, `--border`, `--muted`).
   L'ÉTAT ne s'exprime que par `StatusPill`/`--stage-*` (étape lead) et les tones de `ui/Badge`
   (success/warning/danger/info). Le brass `--primary` est réservé à UN CTA par zone
   (« Devis automatique »). L'accent module CRM `--module-accent-azur` ne sert qu'au liseré
   du bandeau (2px) — jamais aux fonds.
2. **Étape = StatusPill, partout** : le `<select>` d'étape disparaît ; le `StageControl` rend
   la rangée des 6 pills (`statusTone()` mappe déjà new/contacted/quote_sent/follow_up/signed/
   cold), courante pleine, autres fantômes cliquables. Clés depuis `features/crm/stages.js`
   (miroir CI de STAGES.py) — jamais une liste locale.
3. **Échelle typo stricte** (recon 03 #34) : nom du lead `--text-h2`, titres de section
   `--text-h3`, corps `--text-body`, labels/méta `--text-small`, RIEN d'autre. Tous les
   montants/kWc/m³ en `.num` + `tabular-nums`.
4. **Rythme d'espacement** : grille 8px — `gap: var(--space-4|-6)` équivalents Tailwind
   `gap-2/gap-3/gap-4` uniquement ; padding de Card unifié ; densité pilotée par
   `[data-density]` (les hauteurs de contrôle suivent `--control-h`).
5. **Élévation** : zones du workspace = `shadow-card` (liseré 1px, jamais flottant au repos) ;
   seuls Dialog/Sheet/menus portent `shadow-modal/menu`. Z-index via l'échelle `--z-*`.
6. **Dark mode STRICTEMENT par tokens** : interdiction de hex nu dans tout code LW. Les 4
   fallbacks de tokens inexistants (`--color-success-muted` & co, recon 04 §1) meurent avec
   la migration des chips vers `ui/Badge`. `.lead-dup-warning`, `.lead-gps-link`,
   `.lead-bill-error` → `--warning`/`--info`/`--destructive`. `components/Avatar.jsx` remplacé
   par `ui/Avatar` + `--owner-color-1..10`.
7. **Motion** : fast-in/slow-out — entrée `--motion-fast` (120ms), sortie `--motion-base`
   (180ms), `--ease-standard` ; UNIQUEMENT transform/opacity (règle Linear, recon 03 #25) ;
   `field-saved-pulse` pour la confirmation d'autosauvegarde ; `DealSignedCelebration` réservé
   au moment Signé ; `prefers-reduced-motion` déjà zéroé par les tokens — ne rien réanimer à la main.
8. **Skeleton à l'ouverture** : `useDelayedLoading` + `FadeSwap` + `Skeleton*` en forme de la
   vraie grille (rail/centre/rail) pendant le GET complet ; jamais de spinner nu, jamais
   `animate-pulse` brut.

---

## D5 — À NE PAS FAIRE (liste ferme)

- **Jamais toucher `apps/ventes/quote_engine/`** ni aucun chemin PDF devis (règle #4) ; le
  workspace ne fait que POINTER vers les modes existants du LeadDevisPanel.
- **Clés d'étape uniquement via `features/crm/stages.js`** (miroir STAGES.py, règle #2) ; ne
  jamais inventer/renommer une étape ; ne construire AUCUN nouveau modèle de funnel (le champ
  `Lead.stage` existant suffit — la note FUTURE INTENT de la règle #2 vise un futur moteur, pas
  cette fenêtre).
- **`DocumentStageTrack` jamais pour le funnel lead** — réservé à la chaîne DOCUMENT
  (devis→facture→chantier) dans les cartes de l'onglet Devis.
- **Zéro nouvelle dépendance npm.** Radix/Tailwind/lucide/sonner existants suffisent.
- **Zéro migration destructive** — UNE seule migration additive autorisée
  (`LeadActivity.pinned`).
- **`Produit.prix_achat` / marge : jamais client-facing** — n'apparaît nulle part dans cette
  fenêtre.
- **Jamais snap/rejeter une valeur tapée** : formulaires `noValidate`, inputs `step="any"`
  (garde héritée du générateur) ; la canonisation téléphone est un ÉCHO SERVEUR, jamais un
  reformatage à la frappe.
- **Ne pas toucher** `apps/web`, le formulaire contact (parké), la voie legacy WeasyPrint,
  `LeadExpressModal`, `LeadInsightsDialog`, le webhook leads.
- **Multi-tenant** : tout ajout backend garde `company` scoping + `request.user.company`
  (patrons existants du viewset).
- **Contrat e2e jamais cassé en silence** : chaque déplacement de hook DOM met à jour la spec
  dans la MÊME tâche (LW40) ; `#lf-nom`, `.modal-title` « Lead — », `.ap-*`, `.act-*`,
  `a.att-name`, `.ldp-*`, sélecteurs SigneDialog sont CONSERVÉS tels quels.
- **Pas de refactor adjacent** : ClientForm, DevisGenerator, kanban/list views hors périmètre
  (sauf les 2 lignes de câblage d'ouverture).

---

## CARTE DES FICHIERS CIBLES — `frontend/src/features/crm/workspace/` (14 fichiers)

| # | Fichier | Rôle | Contrat (props / exports) |
|---|---|---|---|
| 1 | `LeadWorkspace.jsx` | Shell : variants dialog/page, bandeau (queue nav ◀▶ i/n, titre, chip save-state, bannière stale, ✕), grille 3 zones, câblage raccourcis + leaveGuard | `{ lead, onClose, onSaved, leadsQueue?, onNavigateLead?, initialDevis?, focusSection?, variant='dialog' }` — le contrat LeadForm actuel, inchangé pour les appelants |
| 2 | `useLeadDraft.js` | Hook moteur d'état (voir D2) : autosave, flush, leaveGuard, miroir sessionStorage, garde stale | `useLeadDraft(lead, { mode }) → { state, setField, flush, leaveGuard, dispatch }` |
| 3 | `draftCore.js` | Réducteur PUR + `canonEq` + `diff` + merge réponse — zéro React, testé en `.mjs` node:test | `reducer(state, action)`, `canonEq(a,b)`, `applyFlushSuccess(state, res)` |
| 4 | `IdentityRail.jsx` | Zone gauche : identité, score+raisons, triade, chips QX28, bannières (doublons/client_match/carte), pile d'actions | `{ state, onAction(type), users }` |
| 5 | `StageControl.jsx` | Rangée StatusPill 6 étapes + rotting + interception SIGNED→SigneDialog + toast recul-400 + raccourcis 1-4 | `{ state, onStageChanged }` |
| 6 | `SectionsPane.jsx` | Zone centre : registre de sections, nav-chips sticky scroll-spy (rAF), repli persisté, wrapper `<form>` en création | `{ state, setField, mode, registry }` |
| 7 | `sections/SectionPipeline.jsx` | Suivi commercial (sans stage) : type_installation, owner, relance, montant_estime, date_cloture, priorité, canal, langue, tags, contact_preference, perdu/motif | chaque section : `{ state, setField, errors }` — présentation pure, AUCUN état propre |
| 8 | `sections/SectionContact.jsx` | Contact & site : nom (#lf-nom, paste-carte), prénom, tel/whatsapp (PhoneHint, paste-clean), email, société, ville, adresse, GPS + lien carte, bannière dup live VX239 | idem |
| 9 | `sections/SectionEnergie.jsx` | Énergie (facture hiver/été, ete_differente, conso, tranche, raccordement, 82-21) + POMPAGE (agricole : cv/hmt/débit, req-auto) | idem |
| 10 | `sections/SectionSite.jsx` | Toiture & site : type/surface/kWc/batterie/orientation/inclinaison/ombrage/structure/étages | idem |
| 11 | `sections/SectionVisite.jsx` | Visite : visite_prevue/effectuee/notes + `AppointmentBooker` embarqué (satellite conservé en place) | idem |
| 12 | `sections/SectionDivers.jsx` | Origine web (DefinitionList RO, repliée) + Note générale + `CustomFieldsInput` — ENFIN dans la nav | idem |
| 13 | `ContextRail.jsx` | Zone droite : shell `ui/Tabs` + badges de compte + onglets minces Activités (ActivitiesPanel + plan) et Pièces (AttachmentsPanel) | `{ state, refreshHistorique, users }` |
| 14 | `TimelineTab.jsx` + `DevisTab.jsx` | Historique (chatter+composer+filtre+épingle+points-contact) ; Devis (cartes chaîne, CTA devis_auto, WhatsApp) | `{ state, dispatch, … }` |

Satellites INCHANGÉS de place : `pages/crm/leads/{AppointmentBooker,SigneDialog,
PlanActiviteDialog,ConvertirClientDialog,LeadDevisPanel}.jsx` (corrigés lane 0/6).
`pages/crm/LeadForm.jsx` devient un adaptateur mince (re-export) puis est retiré quand les
appelants et tests ont migré. CSS : bloc `/* ── Lead Workspace (LW) ── */` APPEND-ONLY dans
`index.css` (`.lw-*` uniquement, tokens only) ; les classes `.lead-*` orphelines purgées en fin
de run.

### Backend (additif seulement, `apps/crm/`)
- `historique/` : `select_related('user','attachment')` (fix N+1 confirmé, views.py:944-950).
- `LeadActivity.pinned` (Boolean default False) + UNE migration + actions
  `epingler/desepingler` + tri pinned-first du serializer.
- `TRACKED_FIELDS` +11 champs métier (montant_estime, date_cloture_prevue, distributeur,
  project_timeline, financing_intent, facility_type, site_count, visit_window_part,
  visit_window_week, roof_age, ownership) — jamais utm/meta/custom_data.
- `pii_masked` booléen calculé sur LeadSerializer.
- `chatter_recent` (50 dernières, select_related) embarqué UNIQUEMENT sur retrieve — l'ouverture
  de la fenêtre passe de 4 requêtes à 3.

---

## CONTRAT E2E (décisions, cf. recon 07)
CONSERVÉS byte-identiques : `#lf-nom` ; `.modal-title` contenant « Lead — »/« Nouveau lead »
(le bandeau LW rend un `DialogTitle className="modal-title"`) ; `.modal-close` ; `.ap-*` ;
`.act-*` ; `a.att-name` ; `.ldp-*` + `data-testid="lead-devis-panel"` ; sélecteurs SigneDialog ;
boutons « + Nouveau lead », « Créer le lead », /Devis automatique/, /Édition complète/.
MIS À JOUR dans LW40 (même tâche que la spec) : « Mettre à jour » → « Enregistrer » (bandeau) ;
`.lead-summary-bar`/`data-testid="lead-summary-bar"` → `data-testid="lw-identity-rail"` ;
`.lead-bill-view`/`.lead-bill-input` → champs normaux de SectionEnergie (spec réécrite sur
`#lf-facture-hiver`) ; `.form-group hasText 'Responsable'` → stable via label.

## ORDRE DE BUILD (résumé lanes — détail dans plan2-tasks-draft.md)
Lane 0 (urgence, d'abord, commits autonomes) → Lane 1 (décomposition, séquentielle) →
Lanes 2/3/4/6 (parallèles, file-disjointes sur la carte ci-dessus) ; Lane 5 backend en
parallèle de tout ; Lane 7 tests/e2e en dernier (@after les lanes UI).
