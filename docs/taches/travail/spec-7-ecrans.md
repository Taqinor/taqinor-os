# Spec 7 — L'ensemble : navigation, vocabulaire, écrans (`features/taches`)

Loi : `recherche-7-simplicite.md` (« R7 »). Chemins relatifs à `frontend/src/`. Noms d'API inchangés ; seuls les mots montrés changent.

## 1. Modèle mental (le test)

1. « Je note tout ici, d'un geste ; ce qui n'a pas de place attend dans **À trier**. »
2. « Chaque matin je fais mon **plan du jour** : ce que je fais, et mon **essentiel**. »
3. « **Aujourd'hui** me montre tout ce que j'ai à faire, ce que l'ERP attend de moi compris. »
4. « Le reste vit dans ses **projets** ; l'**agenda** me montre quand. »
5. « Le soir je fais le **bilan**, en fin de semaine la **revue** ; le **Copilote** m'aide à décider et à garder mon rythme. »

Hors de ces phrases → AVANCÉ (étiquettes, vues, modèles, burn-up, groupes, constats).

## 2. Navigation

Barre du bas : 5 onglets dont « Apps » ; ≤ 4 sections → toutes directes (`components/layout/BottomTabBar.jsx:33-48`).
`nav.items` = 4 (le 1er = porte, `crm/module.config.jsx:83-88`), lus aussi par la barre latérale (`lib/apps/ActiveAppContext.jsx:153-158`).

| Onglet | Route | Pastille |
|---|---|---|
| Aujourd'hui | `/taches/aujourdhui` (`/taches` y redirige) | — |
| À trier | `/taches/a-trier` | nombre (masqué à 0) |
| Projets | `/taches/projets[/:id]` | — |
| Agenda | `/taches/agenda?vue=jour\|semaine\|mois\|a-venir` | — |

**Le seul « Plus »** : ⋯ dans la ligne de titre de chaque écran (en-tête global trop serré, spec 6a §9 d) : 1 à 3
actions de l'écran, puis Revue de la semaine · Mon rythme · Supprimées récemment · Réglages ; à côté, la loupe.
**Ajouter** : bouton flottant iPhone (`ui/FloatingActionButton.jsx:6`) ; bureau : champ en tête de liste.
Fiche : `?tache=<id>` ; rituels : `/taches/aujourdhui?ouvrir=plan|bilan` ; autres sous `/taches/` : `revue`, `rythme`,
`recherche`, `supprimees`, `reglages/…`, `projets/archive|modeles`. Ouverture : Aujourd'hui.

| Fonction | Où | Gestes depuis Aujourd'hui |
|---|---|---|
| Ajouter, coller une liste, dicter | bouton flottant → feuille de saisie | 1 |
| Cocher · Reporter | case · balayage gauche (fiche → Reporter) | 1 · 1 (2) |
| Fiche : notes, check-list, Quand, Échéance, Projet, Priorité | toucher la ligne | 1 |
| Heure, rappel | fiche → Quand → Heure / Rappel | 3 |
| Répéter, étiquettes, durée, en attente de, après…, jalon, lié à, confidentielle, découper | fiche → Plus → champ | 3 |
| Déplacer, en attente, essentiel, sélectionner, réorganiser | appui long → choix | 2 |
| À trier, suggestions de l'ERP, convertir les à-faire | onglet | 1 |
| Un projet · Un jour · En pause | Projets → ligne | 2 |
| Planifier le projet | Projets → projet → bandeau ou ⋯ | 3 |
| Tableau, Chronologie, avancement détaillé, décaler, modèle, terminer, archiver | Projets → projet → ⋯ → choix | **4** |
| Archive, Modèles | Projets → ⋯ → choix | 3 |
| Agenda · placer à une heure | onglet · À placer → tâche → créneau | 1 · 3 |
| Plan du jour, bilan du soir | bandeau, ⋯ ou notification | 1-2 |
| Planifier avec le Copilote | ⋯ → bouton (aussi dans le plan) | 2 |
| Recherche · filtres · vues | loupe · Filtres · Enregistrer | 1 · 2 · 3 |
| Revue, Mon rythme, Supprimées récemment | ⋯ → choix | 2 |
| Mode du rythme, Ce que j'ai remarqué | ⋯ → Mon rythme → choix | 3 |
| Congés, jours courts, temps disponible | ⋯ → Mon rythme → Mes jours → champ (ou dit au Copilote) | **4** |
| Notifications, Mon iPhone, Vie privée, L'ERP me suggère | ⋯ → Réglages → rubrique | 3 |
| Exporter, Tout effacer, réglages avancés | ⋯ → Réglages → rubrique → bouton | **4** |

Les **4** : rares, à ≤ 2 gestes de leur écran (R7 règle 3) ; « Tout effacer » éloigné exprès.

## 3. Vocabulaire fermé (écrans, notifications, Copilote, tuile, flux)

| Terme | Définition | Interdits |
|---|---|---|
| Tâches | l'app | to-do |
| **Aujourd'hui** | l'écran du jour | Ma journée (déjà `installations/module.config.jsx:81` et `visites/module.config.jsx:51`), Mon jour |
| À trier | reçu, pas encore rangé | boîte de réception, inbox |
| Projet · Étape · Jalon | résultat à atteindre · partie d'un projet (`Section`) · tâche-repère | section, phase, milestone ; « domaine » montré « Groupe » |
| Check-list · point | cases dans une tâche | étapes |
| Sous-tâche | tâche sous une tâche (« Découper ») | étape |
| Quand | jour prévu ; puce « jeu. 19 » | planifiée le |
| Échéance | date limite ; puce « échéance ven. 20 » | deadline, due |
| Demain | toujours J+1 ; un report ailleurs dit sa date (« lun. 23 ») | — |
| Reporter | une tâche à plus tard (défaut : prochain jour travaillé) | décaler, repousser, replanifier |
| Choisir un jour | n'importe quel jour | replanifier |
| Décaler les dates | tout un projet de N jours | — |
| Un jour | sans jour, gardée | plus tard, peut-être |
| Passer | quitter un rituel ou une étape sans rien changer | plus tard, ignorer |
| Pas maintenant | refuser une proposition qui reviendra | — |
| Essentiel(le) | 1 à 3 tâches du plan du jour | important(e), focus, top |
| Priorité haute/moyenne/basse | l'échelle unique | urgent, P1 (frappe seule) |
| À décider | prévue un jour passé, reportée 3 fois, ou échéance proche sans jour | en retard, à trancher |
| Abandonner | ne plus faire (`annule`, gardée) | annuler |
| Annuler | défaire le dernier geste | — |
| Supprimer · Supprimées récemment | retirer, 30 jours pour restaurer | corbeille (celle de l'ERP est commune) |
| En attente de… | attend quelqu'un ou quelque chose | bloquée |
| Après… | commence après une autre tâche (`bloquee_par`) | attend, dépend de |
| Plan du jour · Faire le plan | rituel du matin | planning |
| Bilan du soir · Faire le bilan | rituel du soir | clôture, clore |
| Revue de la semaine | rituel hebdomadaire, remplace le bilan ce jour-là | bilan hebdo |
| Planifier le projet · À planifier | 2 minutes guidées · pas encore fait | phase de planification |
| Projet de la semaine | mis en avant 7 jours | focus |
| Copilote | l'assistant de l'ERP (`features/ia/CopilotPanel.jsx:141`) | coach, IA, assistant, agent |
| Mon rythme · objectif du jour | l'écran · nombre de tâches visé | palier, bloc, zone, score |
| En faire plus · Garder ce rythme · Sans objectif | les modes `pousser`/`tenir`/`libre` | pousser, tenir, libre |
| Plan tenu · Objectif atteint | faites parmi les prévues · compte ≥ objectif | journée réussie/ratée, série, échec |
| Durée · temps disponible | d'une tâche · minutes de travail par jour | estimation, capacité, charge |
| Rappel | alarme posée par lui | alerte |
| Point de la journée | l'unique notification de journée | relance (mot du CRM, `crm/module.config.jsx:109`) |
| Activité ERP · Lié à | activité de l'ERP · lien vers une fiche | tâche ERP |
| Confidentielle | jamais montrée au Copilote ni en titre hors de l'app | privée (tout l'est) |
| Faites | tâches cochées | terminées |

Jours « travaillés », jamais « ouvrés » ; durées « 25 min ».

## 4. Les écrans

Partout : un bouton plein ; section vide absente ; squelette après 1 s, jamais sur une liste affichée ; erreur = la liste
reste + « Pas à jour — 09:02 · Réessayer » ; hors ligne = dernier état, ajouts en file (spec 6b §8), autres gestes grisés ;
vide = une phrase + un bouton (« Rien de prévu aujourd'hui. » + Faire le plan).

| Écran | Action principale | Visible d'emblée | Replié | Bureau |
|---|---|---|---|---|
| Aujourd'hui | Ajouter | anneau « 4/6 · essentiel 1/2 · plan 3/5 » ; bandeau Faire le plan ; Essentiel ; Aujourd'hui (heures fixes en tête, activités ERP, visites, interventions, « Suivi des relances : 5 ») ; Ce soir | À décider, En attente, Faites, Ailleurs dans l'ERP ; temps et objectif (toucher l'anneau) | colonne droite : agenda du jour |
| Saisie (liste collée : aperçu, « Créer N tâches ») | Ajouter (Retour) | champ, puces lues (×), Quand · Projet · Priorité | étiquette, durée ; Ranger par projet | en ligne ; `c t` = dialogue |
| Fiche | Fait | titre, Quand · Échéance · Projet · Priorité, notes, check-list, Reporter | Plus ; Découper avec le Copilote ; Supprimer | panneau droit |
| À trier | (par ligne) | Suggéré par l'ERP ; lignes Aujourd'hui · Demain · Projet… · ⋯ ; à-faire à convertir | Un jour, Garder sans projet ; Copilote ; une par une | boutons au survol |
| Agenda | Ajouter (jour hérité) | Jour · Semaine · Mois · À venir ; ← Aujourd'hui → | À placer ; affichage | grille horaire, glisser (iPhone : 7 lignes, toucher puis créneau) |
| Projets | Ajouter | actifs (nom, 12 sur 20, icône à surveiller, À planifier) ; Nouveau projet ; Un jour | En pause ; ⋯ : Archive, Modèles, Trier par priorité | colonne des projets + projet ouvert |
| Un projet | Ajouter (projet hérité) | fini quand…, échéance, 12 sur 20, santé, prochain jalon ; étapes | Faites ; ⋯ : vues, Décaler, Planifier, Modèle, Pause, Terminer | vues visibles |
| Planifier le projet | Suivant / Terminer | fini quand… · échéance (puces) · premières actions | étapes, jalons, risque ; Copilote | dialogue |
| Plan du jour | Valider le plan | À décider → proposition cochée, « 3 h 10 pour 4 h », objectif → ★ 0 à 3 | proposition de rythme ; Copilote | = |
| Bilan du soir | Valider | faites ; par reste : Demain · Choisir un jour · Un jour · Abandonner ; « Le reste → lun. 23 » ; 4 faits | un mot (280 car.) | = |
| Revue de la semaine | Terminer la revue | 4 faits ; carte par projet (Garder · Pause · Terminer · Passer) ; projet de la semaine | intention, constat, Un jour | toutes les cartes |
| Mon rythme | (le mode) | objectif + source ; 3 modes ; 14 jours ; proposition | remarqué, Mes jours, Comprendre mon rythme | = |
| Recherche | — | champ ; Faites aussi · Projet ▾ · Priorité haute | 7 autres filtres, tri, groupe, Enregistrer | `/` |
| Réglages | — | Notifications · Mon iPhone (5 étapes, spec 6b §9) · Vie privée (socle §2.7, §8) · L'ERP me suggère · Mes données | Avancé ; jetons | = |
| Supprimées récemment | Restaurer | 30 jours | Derniers gestes | = |
| Carte cockpit « Tâches · Aujourd'hui » | Ouvrir | « 4 à faire · 2 faites », 3 lignes cochables | — | = |

## 5. Gestes et clavier

| Geste sur une ligne | Effet, partout | Équivalent visible |
|---|---|---|
| Toucher la case | Fait / défait ; la ligne reste, barrée, jusqu'à la sortie de l'écran | — |
| Toucher le reste | fiche | — |
| Balayage gauche | révèle Reporter (au jour nommé) + Choisir un jour ; complet = Reporter ; estampille « → lun. 23 » en place | fiche → Reporter |
| Balayage droite | révèle Fait ; complet = Fait | case |
| Appui long | Choisir un jour · Déplacer… · Essentiel · En attente · Priorité · Sélectionner · Réorganiser · Supprimer | fiche |
| Glisser | iPhone : en mode Réorganiser seulement (poignées, ▲▼) ; bureau : direct | ▲▼, `Alt+↑/↓` |

Écriture → toast « … · Annuler » 6 s (`lib/mutateWithUndo.js:39`), puis Derniers gestes. Supprimer : jamais par
balayage, sans dialogue depuis un menu (réversible). Clavier muet sous un dialogue (`providers/focusedRecordShortcuts.jsx:98-113`) ;
**aucune touche seule ne fait disparaître une ligne** (règle maison du 02/10) : elle reste, estampillée.

| Touche | Effet |
|---|---|
| `c t` · `g j` (partout) | Créer une tâche · Aujourd'hui (`shortcut:'j'` du module, `providers/shortcuts.js:69` ; `g t` = SAV, `:35`) |
| `n` · `/` · `?` · Ctrl/⌘ K | ajouter ici · chercher · aide · palette |
| `j` `k` · Entrée · Échap | ligne suivante/précédente (`shortcuts.js:141`) · fiche · fermer |
| Espace · `d` · `m` · `x` · `h` | Fait · Quand (Entrée = Reporter au jour proposé) · Déplacer · Sélectionner · Heure |
| `Alt+↑/↓` · `Maj+↓` · Ctrl/⌘ Z | réordonner · bloc +15 min · annuler |
| Agenda : ← → · `t` | période · aujourd'hui |

Palette : Créer une tâche, Nouveau projet, Faire le plan, Faire le bilan, les 4 onglets ; « Supprimer/Abandonner
« titre » » avec dialogue qui nomme la tâche. Chaque menu montre sa touche.

## 6. Parcours chiffrés (gestes hors texte)

| # | Parcours | iPhone | Bureau | Cible |
|---|---|---|---|---|
| 1 | Demain dans un projet | + · « … demain #Polydesign » · Retour = 2 | `n` · Entrée = 2 | 2 / 2 |
| 2 | Nouveau projet | idem, « #SiteWeb » = 2 | 2 | 2 / 2 |
| 3 | Cocher | 1 | Espace 1 | 1 / 1 |
| 4 | Reporter à demain | balayage 1 (fiche → Reporter 2) | survol 1 ; `d` Entrée 2 | 1 / 1 |
| 5 | Choisir un autre jour | balayage · Choisir · jour = 3 | survol Quand · jour = 2 | 3 / 2 |
| 6 | Déplacer dans un projet | appui long · Déplacer · projet = 3 | `m` · Entrée = 2 | 3 / 2 |
| 7 | Plan du jour (3 à décider, 2 essentielles) | 1 + 3 + 2 + 1 = 7 | 7 | 2 + choix |
| 8 | Bilan du soir | ouvrir · « Le reste → lun. 23 » · Valider = 3 | 3 | 3 |
| 9 | Vider À trier (3 vers projets, 2 datées) | 1 + 3×2 + 2 = 9 ; Copilote 3 | 9 | 1 + ≤ 2 par tâche |
| 10 | Créer et planifier un projet | Projets · Nouveau · Créer · Suivant · puce · Terminer = 6 | 6 | 6 |
| 11 | Poser un rappel | ligne · Quand · Rappel = 3 (tapé : 0) | 3 | 3 |
| 12 | Copilote, prioriser | ⋯ · Planifier avec le Copilote · Adopter = 3 | 3 | 3 |

Cibles 1-6 : R7 §3 ; les autres posées ici. KLM du 1 au bureau ≈ 7,75 s ≤ 8 s. Au-dessus : seul le 4 au clavier
(+1, règle maison). Repris : 8 (spec 3 : n + 2 ; lot nommé), 10 (spec 4 : 8 hors onglet ; planification ouverte d'office).

## 7. Première utilisation

Pas de visite guidée. Aujourd'hui vide : « Colle ou dicte tes listes : je les range par projet. » + **Coller mes listes**
(D-TCH-4). Trois gestes : coller (ou dicter) → aperçu (« Maison : » = projet ; **Ranger par projet** si le Copilote est
là) → **Créer N tâches** ; puis **Faire le plan**. Rythme muet : l'objectif 5 n'est que dans le plan, « valeur par défaut ».
Notifications demandées dans Mon iPhone. Une révélation par jour au plus, une fois : lendemain du 1er plan → carte Mon
iPhone ; 1re puce Projet à la main → « tape #Polydesign » ; 3e report par la fiche → « balaie vers la gauche » ; À trier
≥ 5 → Ranger avec le Copilote ; 1er projet → Planifier le projet ; fin de 1re semaine → Revue ; 10e jour évalué → « J'ai
10 jours de toi… » (spec 5a §3.10) ; bureau, 5e ajout souris → « `n`, `?` ».

## 8. Arbitrage final (E essentiel · A avancé · X écarté)

| Fonction | Classe | Correction |
|---|---|---|
| Saisie partout, analyseur FR/EN, puces, chaîne, `#projet` + Nouveau projet, Quand/Échéance, priorité, collage + aperçu + groupes, doublons, Annuler | E | — |
| Rangement par le Copilote | E s'il est disponible | — |
| À trier en un geste, sélecteur de projet, check-list, notes, Un jour, recherche, conversion des à-faire | E | — |
| Étiquettes, durée, récurrence, rappel par la phrase, projet suggéré, une par une, couleur, icône, sous-tâches, en attente de, confidentielle, filtres, tri, groupe, vues, Derniers gestes, sélection multiple, dictée bureau | A | — |
| Captures hors ligne | E, invisible | spec 3 X, spec 2 éditait `offlinesync` : file du module (6b §8) ; autres gestes hors ligne X v1 |
| Glisser-déposer | E bureau, A iPhone | spec 3 : direct iPhone |
| Essentiel, Aujourd'hui, Ce soir, activités ERP, visites, interventions, Suivi des relances | E | bandeau agenda (spec 3) fondu dans les lignes |
| À décider (retards, reportées 3 fois, échéances proches) | E replié | 3 sections → 1 |
| Anneau : faites, essentiel, plan tenu | E ; temps, objectif A | spec 3 : minutes visibles |
| Tout au prochain jour ouvré (liste) | A | — |
| « Le reste → lun. 23 » au bilan | **E** | spec 3 : choix un par un ; les reportées 3 fois exclues |
| Agenda 4 vues, blocs, rappels posés | E | — |
| 3 jours, n° de semaine, jours travaillés seuls, échéances dans l'agenda, rappel avant bloc, nom du férié | A | — |
| Auto-planification, déplacer un événement ERP, maintenance, rappel de lieu, boutons de notification iOS | X | raisons spec 3 |
| Projets : ordre manuel, priorité, statuts, À planifier, couleur d'office, 12 sur 20, santé, négligé, revue, terminer | E | — |
| Constat « n actifs, n ont avancé » | **A** (revue) | spec 4 : E |
| Vues Tableau / Chronologie | A (⋯ iPhone) | spec 4 : sélecteur visible |
| Groupe, Trier par priorité, dates d'étape, jalons, après…, décaler, burn-up, projet de la semaine, modèles, dupliquer, archive | A | — |
| Plusieurs prérequis, Gantt, tableau par statut, statut couleur, plafond, OKR, modèles fournis, épingler | X | raisons spec 4 |
| Montée/baisse proposées, Garder ce rythme, 4 faits | E | — |
| Objectif dit au 1er jour | **A** (Mon rythme, Copilote) | spec 5a : carte J1 |
| Sans objectif, jours courts, constats, repère P60 | A | — |
| Points, badges, séries ; P60 objectif ou borne ; heures imposées | X | raisons spec 5a |
| Boutons « … avec le Copilote » | A (⋯, plan, fiche, À trier, Mon rythme) | spec 5b : sur les écrans |
| Lien ERP (lead, client, devis, facture, chantier, ticket), posé seul depuis la fiche ouverte | E ; à la main A | — |
| ✓+ sur les fiches ERP, suggestions devis accepté / chantier réceptionné ou annulé | E | — |
| 9 autres cibles, visite validée, suggestions société, Ailleurs dans l'ERP | A | — |
| Chatter, Ma file, visites liées, autres suggestions | X | raisons spec 6a |
| Pastille, notifications, accueil, carte cockpit, Mon iPhone, flux, Siri, tuile, export, tout effacer | E (les 6 derniers en Réglages) | — |
| Raccourci de manifeste « Tâches » | A | spec 6b : « Mes tâches » |

**Replié davantage** (R7 §1 Hick, règle 12 ; à ≤ 2 gestes) : constat,
vues iPhone, minutes, 7 filtres sur 10, heure et rappel (dans Quand), objectif J1, glisser iPhone, phrase de santé
(icône en liste), priorité (drapeau si haute). **Déplié** : « Le reste → lun. 23 », chaque ligne montrant son jour.

## 9. Composants (`features/taches/ui/` ; vers `ui/`, unité deploy `docs/ownership.yml:805`, au 2e usage)

| Composant | Réutilise | Accessibilité | Acceptation |
|---|---|---|---|
| `LigneTache` | patron `useSwipeReveal` (`ui/datatable/DataTable.jsx:183`, recopié), `ContextMenu` | balayage = item de menu (WCAG 2.5.1, 2.5.7) ; `aria-live` « Reportée à lun. 23 » | ≥ 60 % = Reporter ; ligne retirée au rechargement seulement |
| `CaseRonde` | `Checkbox` (`ui/Checkbox.jsx:16`, 18 px) dans une cible de 44 px | Espace ; contour 3:1 ; mouvement réduit | coche < 0,1 s, retour arrière si échec |
| `SelecteurQuand` (+ Heure, Rappel) | `DatePicker`, `TimePicker`, `Segmented`, `ui/date-utils.js` | `radiogroup` | Demain = J+1 ; jour non travaillé signalé, jamais refusé |
| `ChampSaisie` à jetons | `Input`, `useDraftAutosave`, `useKeyboardAwareScroll` | puces annoncées ; × nommé | annexe A spec 2 ; texte jamais perdu |
| `FeuilleACrans` 50/85 % | `Sheet` (`ui/Sheet.jsx:15`, sans crans) + CSS | poignée = bouton, Échap, focus piégé | brouillon gardé à la fermeture |
| `GrilleAgenda` | `@dnd-kit/core`, `dndA11y.js` | toucher puis créneau ; `h`, `Maj+↓` | chevauchements côte à côte |
| `Tableau` | `usePanScroll`, `kanbanA11y.js` | « Déplacer vers… » | ordre gardé |
| `AnneauProgression` | SVG sur jetons | `role=img` + « 4 sur 6 » | jamais un % seul |
| `SelecteurProjet`, `ApercuListe` | `Combobox` ; `Checkbox` | clavier complet | doublon refusé au champ ; même rendu écran et carte `capture_apercu` |

## 10. Incohérences entre specs (côté utilisateur) et résolution

| Incohérence | Résolution |
|---|---|
| « Ma journée » (3, 5b, 6a, 6b) = deux écrans existants | Aujourd'hui |
| `/taches` (6a), `/taches/aujourdhui` (6b), `?tache=` (3), `/taches/bilan` (6b), `/taches/taches/<id>` (5b §6) | routes du §2 ; fiche par `?tache=` + `detail.tache_id` |
| `g t` (3) déjà au SAV ; « coach » (5b) ≠ « Copilote » du panneau | `g j` ; Copilote |
| À décider, à trancher, en retard, échéances proches (3) | une section |
| bandeau agenda (3) + obligations (6a) ; « à convertir » sur Ma journée (6a) et la Boîte (2) | lignes ; À trier seul |
| demain = J+1 (2) ou prochain jour ouvré (3) | J+1 ; le report nomme son jour |
| toast 6 s (code) / 8 s (R7, non sourcé) ; trois annulations (`GesteAnnulable` 2, `Annulation` 5b, `decaler/annuler` 4) | 6 s + Derniers gestes ; un bouton, un modèle |
| glisser iPhone 150 ms (3) / mode réorganiser (4) / appui long = menu (R7) | menu ; mode Réorganiser |
| `heure_prevue` (2) / `heure_debut` (3) ; « étapes » = sections (4), points (2), sous-tâches (5a) | `heure_debut` ; Étape = section |
| « Plus tard » (3, 4), « Corbeille » (2), « Tâche privée » (5b), « attend » (4), « 1 importante » (6b), « En retard » (2), « relance » (socle §5) | §3 |
| rythme réglé à deux endroits (5a, 5b) ; revue en trois morceaux (4, 5a, 5b) ; dépôt sur la barre latérale (2), générique | Mon rythme ; Revue ; colonne de l'écran Projets |
| « Mes tâches » (6b manifeste, 6a carte) ; bouton d'accueil permanent (6a, 6b §7) | « Tâches », « Tâches · Aujourd'hui » ; carte unique + Mon iPhone |

## 11. Auto-évaluation (grille R7)

Heuristiques (0-2) : 2 partout sauf reconnaître 1 (`#projet`, balayages, appui long invisibles, compensés), minimalisme 1
(Aujourd'hui rempli : 5 blocs), aide 1 (iPhone : astuces seules) = **17/20**.
Parcours cognitif (but · voit l'action · la relie · voit le progrès) : 1 — **non** à « voit l'action » pour `#` et
« demain » tapés ; par les puces oui, mais 4 gestes au lieu de 2. 4 — balayage **non** au 1er usage ; fiche → Reporter
oui, 2 = cible « 2 taps ». 6 — appui long **non** ; fiche → Projet → choix oui, 3 = cible.
Cibles : iPhone tenues (chemin expert) ; bureau c clavier 2 ; e = 0 après « En faire mon accueil ». 20 règles : 18 oui
(9 non au clavier, 14 partielle). WCAG : conçu, non mesuré.

## Choix par défaut et objection

« Aujourd'hui » : le mot de tous (celui de Publicité, `adsengine/module.config.jsx:102`, reste dans son app). « À trier » :
tient dans un onglet. Le Copilote garde son nom. Composants chez `taches`.
**Objection** : le socle dit « Ma journée », jamais tranché par le fondateur (spec 6a) ; la route `aujourdhui/` reste.
