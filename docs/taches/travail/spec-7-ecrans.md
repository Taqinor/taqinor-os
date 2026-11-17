# Spec 7 — L'ensemble : navigation, vocabulaire, écrans (`features/taches`) — révision 2

Loi : `recherche-7-simplicite.md` (« R7 »), `arbitrages.md` A11-A14. Chemins : `frontend/src/`. API inchangée.

## 1. Modèle mental (le test)

1. « Je note tout ici d'un geste ; ce qui n'a pas de place attend dans **À trier**. »
2. « Chaque matin l'ERP me **propose** ma journée ; je **garde** ce que je fais et je choisis mon **essentiel**. »
3. « **Aujourd'hui** montre tout ce que j'ai à faire, ce que l'ERP attend de moi compris. »
4. « Le reste vit dans ses **projets** ; l'**agenda** me montre quand. »
5. « Le soir le **bilan**, en fin de semaine la **revue** ; le **Copilote** m'aide à décider et à tenir mon rythme. »

Hors de ces phrases → AVANCÉ (étiquettes, vues, modèles, burn-up).

## 2. Navigation

Barre du bas : 5 onglets dont « Apps » ; ≤ 4 sections → toutes directes (`components/layout/BottomTabBar.jsx:33-48`).
`nav.items` = 4 (le 1er = porte, `crm/module.config.jsx:83-88`), lus aussi par la barre latérale (`lib/apps/ActiveAppContext.jsx:153-158`).

| Onglet | Route | Pastille |
|---|---|---|
| Aujourd'hui | `/taches/aujourdhui` (`/taches` y redirige) | — |
| À trier | `/taches/a-trier` | nombre (masqué à 0) |
| Projets | `/taches/projets[/:id]` | — |
| Agenda | `/taches/agenda?vue=jour\|semaine\|mois\|a-venir` | — |

**Le seul « Plus »** : ⋯ dans la ligne de titre : actions de l'écran (Aujourd'hui : Alléger ma journée, Sélectionner),
puis Revue · Mon rythme · Supprimées récemment · Réglages ; à côté, la loupe. **Copilote** : bouton global
(`components/layout/Header.jsx:210-219`, iPhone non vérifié), 4 demandes prêtes : « Planifie ma journée », « Aide-moi à
prioriser », « Range ma liste », « Où j'en suis ? » ; sans clé, une phrase dit pourquoi (A12). **Ajouter** : bouton
flottant iPhone (`ui/FloatingActionButton.jsx:6`). Fiche `?tache=<id>` ; `aujourdhui?ouvrir=bilan|alleger`.
**Pastille** (corrige 6b §2) : lignes ouvertes d'Essentiel, Prévu, Ce soir et de Proposé montré.

| Fonction | Où | Gestes depuis Aujourd'hui |
|---|---|---|
| Ajouter, coller une liste, dicter | bouton flottant → feuille de saisie | 1 |
| Cocher · Reporter | case · balayage gauche (fiche → Reporter) | 1 · 1 (2) |
| Garder la proposition · essentiel | « Garder ces N » · ★ sur la ligne | 1 · 1 |
| Fiche (notes, check-list, Quand, Échéance, Projet, Priorité, ★) | ligne | 1 |
| Heure, rappel | fiche → Quand → Heure / Rappel | 3 |
| Répéter, étiquettes, durée, en attente de, jalon, lié à, confidentielle, découper | fiche → Plus | 3 |
| Déplacer, réorganiser | appui long (fiche → Projet) | 2 (3) |
| Alléger ma journée · Sélectionner | ⋯ → choix | 2 |
| Copilote et ses 4 demandes | bouton global | 1 · 2 |
| À trier, suggestions ERP, à-faire à convertir | onglet | 1 |
| Un projet · En réserve · En pause | Projets → ligne | 2 |
| Planifier le projet | Projets → projet → bandeau ou ⋯ | 3 |
| Tableau, Chronologie, burn-up, décaler, modèle, terminer, archiver | Projets → projet → ⋯ → choix | **4** |
| Archive, Modèles | Projets → ⋯ → choix | 3 |
| Agenda · placer à une heure | onglet · À placer → tâche → créneau | 1 · 3 |
| Bilan du soir | bandeau du soir ou notification | 1 |
| Recherche · filtres · vues | loupe · Filtres · Enregistrer | 1 · 2 · 3 |
| Revue, Mon rythme (aussi par la progression), Supprimées récemment | ⋯ → choix | 2 |
| Mode du rythme, Ce que j'ai remarqué | ⋯ → Mon rythme → choix | 3 |
| Congés, jours courts, temps disponible | ⋯ → Mon rythme → Mes jours → champ (Copilote : 1) | **4** |
| Notifications, Mon iPhone, Vie privée, L'ERP me suggère | ⋯ → Réglages → rubrique | 3 |
| Exporter, Tout effacer, réglages avancés, agenda externe | ⋯ → Réglages → rubrique → bouton | **4** |

Les **4** : rares, à ≤ 2 gestes de leur écran (R7 règle 3).

## 3. Vocabulaire fermé (écrans, notifications, Copilote, tuile, flux)

| Terme | Définition | Interdits |
|---|---|---|
| **Aujourd'hui** | l'écran du jour (A13) | Ma journée (déjà `installations/module.config.jsx:81`, `visites/module.config.jsx:51`) |
| Prévu · Ce soir | tâches qu'il a mises à aujourd'hui · celles du soir | aujourd'hui (nom de l'écran) |
| Proposé pour aujourd'hui · Garder ces N | prochaines tâches de ses projets, classées par l'ERP · les mettre à aujourd'hui | suggestions, plan proposé |
| Plan du jour · plan tenu | ce qu'il a gardé le matin · « 4 des 5 gardées », dit au bilan | plan 3/5 |
| Alléger ma journée | garder une partie, le reste retourne dans Proposé sans report | décharger |
| À trier | reçu sans projet ni jour | boîte de réception, inbox |
| À revoir | prévue un jour passé, reportée 3 fois, ou échéance proche sans jour ; motif par ligne | à décider, en retard |
| En réserve | gardée sans jour (`quelque_jour`) | un jour, plus tard, peut-être |
| Projet · Étape · Jalon | résultat · partie d'un projet (`Section`) · tâche-repère | section, phase ; « domaine » montré « Groupe » |
| Planifier le projet · À planifier | 2 minutes guidées · pas encore fait | cadrage |
| Check-list · point · sous-tâche | cases dans une tâche · une case · tâche sous une tâche | étapes |
| Quand · « Quand je la fais » | jour prévu, puce « jeu. 19 » · son libellé dans la fiche | planifiée le |
| Échéance | date limite, puce « échéance ven. 20 » | deadline |
| Demain | toujours J+1 ; un report ailleurs dit sa date (« lun. 23 ») | — |
| Reporter · Choisir un jour · Décaler les dates | à plus tard (prochain jour travaillé) · n'importe quel jour · tout un projet | repousser, replanifier |
| Passer · Pas maintenant · Suivant · Fermer | quitter un rituel · refuser, ça reviendra · carte suivante · fermer une feuille | plus tard |
| Essentiel(le) | 1 à 3 tâches choisies (★) | important(e), focus |
| Priorité haute/moyenne/basse | l'échelle unique, tâches et projets | urgent |
| Abandonner · Annuler · Supprimer | ne plus faire (gardée) · défaire un geste (toast) · retirer, 30 jours (Supprimées récemment) | corbeille |
| En attente de… | une personne ou chose, ou une autre tâche (`bloquee_par`) | après, bloquée |
| Bilan du soir · Revue de la semaine | rituel du soir · hebdo, remplace le bilan ce jour-là | clôture |
| Projet de la semaine | mis en avant 7 jours | focus |
| Copilote | l'assistant de l'ERP (`features/ia/CopilotPanel.jsx:141`) | coach, IA, agent |
| Mon rythme · objectif du jour | l'écran · nombre visé, montré « 1 sur 5 » | palier, bloc, zone, score |
| En faire plus · Garder ce rythme · Sans objectif | modes `pousser`/`tenir`/`libre` | pousser, tenir, libre |
| Objectif atteint | compte ≥ objectif | journée réussie/ratée, série |
| Durée · temps disponible | d'une tâche · minutes de travail par jour | estimation, capacité |
| Rappel | alarme posée par lui | alerte |
| Message de 15 h | l'unique notification de journée (heure réglée) | relance (mot du CRM, `crm/module.config.jsx:109`) |
| Activité ERP · Lié à | activité de l'ERP · lien vers une fiche | tâche ERP |
| Confidentielle | jamais montrée au Copilote ni en titre hors de l'app | privée |

Jours « travaillés », jamais « ouvrés ».

## 4. Les écrans

Partout : un bouton plein ; section vide absente ; squelette après 1 s, jamais sur une liste affichée ; erreur = liste
gardée + « Pas à jour · Réessayer » ; hors ligne = dernier état, ajouts en file (6b §8) ; une carte du moment au plus.

**Aujourd'hui, de haut en bas (A14-M1)** : titre, loupe, ⋯ → (1) progression « 1 sur 5 · essentiel 0/2 » (faites sur
OBJECTIF ; toucher → plan tenu, temps, Mon rythme) → (2) carte du moment, le soir « Faire le bilan » → (3) Essentiel →
(4) **Prévu** : heures fixes en tête (visites, poses, blocs), puis tâches et obligations ERP mêlées (> 3 activités sans
heure : une ligne repliable), « Suivi des relances : 5 » → (5) Ce soir → (6) **Proposé pour aujourd'hui** jusqu'à
l'objectif, 1re ligne expliquée (« échéance jeudi · projet prioritaire Ventes »), ★ par ligne, **Garder ces N**, « Voir
toutes les tâches de mes projets » → (7) repliés : À revoir (lot « Tout en réserve »), En attente, Faites, Ailleurs dans
l'ERP. Le matin, 3-5 sont vides : la 1re tâche proposée est visible sans défiler (estimé). Jamais vide tant qu'un projet
actif a une tâche ouverte (A11).

| Écran | Action principale | Visible d'emblée | Replié |
|---|---|---|---|
| Saisie, aperçu | Ajouter / Créer N tâches | champ, puces (×), Quand · Projet · Priorité | Coller encore, Ranger par projet |
| Fiche | Fait | Quand · Échéance · Projet · Priorité, ★, notes, check-list, Reporter | Plus ; « confier = activité ERP » |
| À trier | (par ligne) | Suggéré par l'ERP ; Aujourd'hui · Demain · Projet… · ⋯ | En réserve, Copilote |
| Agenda | Ajouter (créneau vide = son heure) | 4 vues, ← Aujourd'hui →, À placer (n) | affichage |
| Projets | Ajouter | priorité, nom, 12 sur 20, à surveiller, À planifier ; Nouveau projet ; En réserve | En pause, Archive, Modèles |
| Un projet | Ajouter | fini quand…, priorité, échéance, 12 sur 20, santé, jalon ; étapes | Faites ; vues, Décaler, Terminer |
| Planifier le projet | Suivant | priorité + fini quand… · échéance (1 sem → 3 mois, 6 sem) · premières actions | étapes, jalons, risque |
| Bilan du soir | Valider | faites ; par reste Demain · Choisir un jour · En réserve · Abandonner ; « Le reste → lun. 23 » ; plan tenu ; un constat | un mot |
| Alléger ma journée | Garder ces N | lignes du jour, rien de coché | — |
| Revue | Terminer | 4 faits ; carte par projet (Garder · Pause · Terminer · Suivant) ; projet de la semaine | intention |
| Mon rythme | (mode) | objectif + source, 3 modes, 14 jours, proposition | constats, Mes jours |
| Recherche · Réglages · Supprimées | — · — · Restaurer | Faites aussi, Projet, Priorité · 5 rubriques · 30 jours | filtres, vues · Avancé · Derniers gestes |
| Carte cockpit « Tâches · Aujourd'hui » | Ouvrir | « 1 sur 5 », 3 lignes cochables | — |

Bureau : agenda du jour à droite, colonne des projets, glisser, boutons au survol. iPhone : Semaine en 7 lignes. **Retour d'absence (B1)** : fin de congé ou ≥ 3 jours travaillés sans
ouverture → « Tu reviens après 10 jours : 18 tâches attendaient. » [Les remettre dans Proposé] [Les voir une par une] ;
aucun report, notification du matin = tâches du jour. **Mon iPhone (M5)** : carte au 1er « Créer N tâches »,
notifications d'abord ; « Installer le raccourci » si `TACHES_RACCOURCI_SIRI_URL` est posé. **ICS externe (M8)** :
dernière vague (https, adresses publiques, bornes, cache).

## 5. Gestes et clavier

| Geste sur une ligne | Effet, partout | Équivalent visible |
|---|---|---|
| Toucher la case | Fait / défait ; la ligne reste, barrée, jusqu'à la sortie de l'écran | — |
| Toucher le reste | fiche | — |
| Balayage gauche | révèle Reporter (au jour nommé) + Choisir un jour ; complet = Reporter ; estampille « → lun. 23 » en place | fiche → Reporter |
| Balayage droite | révèle Fait ; complet = Fait | case |
| Appui long | Choisir un jour · Déplacer… · Essentiel · En attente de… · Priorité · Sélectionner · Réorganiser · Supprimer | fiche (★ compris) ; ⋯ → Sélectionner |
| Glisser | iPhone : en mode Réorganiser (poignées, ▲▼) ; bureau : direct | ▲▼, `Alt+↑/↓` |

Écriture → toast « Annuler » 6 s (`lib/mutateWithUndo.js:39`), puis Derniers gestes. Supprimer : jamais par balayage. Clavier muet sous un dialogue (`providers/focusedRecordShortcuts.jsx:98-113`) ;
**aucune touche seule ne fait disparaître une ligne** (règle maison du 02/10) : elle reste, estampillée.

| Touche | Effet |
|---|---|
| `c t` · `g j` (partout) | Créer une tâche · Aujourd'hui (`shortcut:'j'` du module, `providers/shortcuts.js:69` ; `g t` = SAV, `:35`) |
| `n` · `/` · `?` · Ctrl/⌘ K | ajouter ici · chercher · aide · palette |
| `j` `k` · Entrée · Échap | ligne suivante/précédente (`shortcuts.js:141`) · fiche · fermer |
| Espace · `d` · `m` · `x` · `h` · `*` | Fait · Quand (Entrée = Reporter au jour proposé) · Déplacer · Sélectionner · Heure · Essentiel |
| `Alt+↑/↓` · `Maj+↓` · Ctrl/⌘ Z | réordonner · bloc +15 min · annuler |
| Agenda : ← → · `t` | période · aujourd'hui |

Palette (partout) : Créer une tâche, **Chercher dans mes tâches** (non indexées, socle §2.4), Nouveau projet, Faire le
bilan, les 4 onglets ; « Supprimer/Abandonner « titre » » avec dialogue nommant la tâche.

## 6. Parcours chiffrés (gestes hors texte)

| # | Parcours | iPhone | Bureau | Cible |
|---|---|---|---|---|
| 1 | Demain dans un projet | + · « … demain #Polydesign » · Retour = 2 | `n` · Entrée = 2 | 2 / 2 |
| 2 | Nouveau projet | idem, « #SiteWeb » = 2 | 2 | 2 / 2 |
| 3 | Cocher | 1 | Espace 1 | 1 / 1 |
| 4 | Reporter à demain | balayage 1 (fiche → Reporter 2) | survol 1 ; `d` Entrée 2 | 1 / 1 |
| 5 | Choisir un autre jour | balayage · Choisir · jour = 3 | survol Quand · jour = 2 | 3 / 2 |
| 6 | Déplacer dans un projet | appui long · Déplacer · projet = 3 | `m` · Entrée = 2 | 3 / 2 |
| 7 | Plan du jour, 2 essentielles | notification · ★★ · Garder ces 5 = 4 | 4 | 2 + ★ |
| 8 | Bilan du soir | notification · « Le reste → lun. 23 » · Valider = 3 | 3 | 3 |
| 9 | Vider À trier (3 vers projets, 2 datées) | 1 + 3×2 + 2 = 9 ; Copilote 3 | 9 | 1 + ≤ 2 par tâche |
| 10 | Créer et planifier un projet | Projets · Nouveau · Créer · priorité · Suivant · puce · Terminer = 7 | 7 | 7 |
| 11 | Poser un rappel | ligne · Quand · Rappel = 3 (tapé : 0) | 3 | 3 |
| 12 | Copilote, prioriser | bouton · demande · Adopter = 3 | 3 | 3 |
| 13 | Retour de 10 jours de congé | ouvrir · Les remettre · Garder ces 5 = 3 (avant ≥ 18) | 3 | 3 |
| 14 | 1re ouverture, 4 notes Apple | 8 pour la 1re (dont 6 d'iOS), 7 par note suivante (Coller encore), Créer = 30 | ≈ 3 par note | — |
| 15 | 15 h, 1 sur 6, alléger | notification · 2 · Garder ces 2 = 4 (sans : 5 ; avant : 5 reports comptés) | 5 | 4 |

Cibles 1-6 : R7 §3. KLM du 1 ≈ 7,75 s ≤ 8 s. Au-dessus : le 4 au clavier (règle maison). Le 14 reste lourd (iOS),
mais juste (M9) ; le 10 paie la priorité (M3).

## 7. Première utilisation

Pas de visite. Aujourd'hui vide : « Colle ou dicte tes listes : je les range par projet. » + **Coller mes listes**
(D-TCH-4) → aperçu (1re ligne suivie de ≥ 2 lignes, ou « Maison : » = « Nouveau projet : … » ; Coller encore) →
**Créer N tâches** → carte Mon iPhone ; le lendemain Proposé est rempli et la notification sonne. Objectif 5 « valeur
par défaut » ; pas de proposition de rythme avant 10 jours. Une révélation par jour, une fois : `#`, balayage, Copilote
(à 5 à trier), Planifier (1er projet), Revue (fin de 1re semaine), « J'ai 10 jours de toi » (5a §3.10), `n`/`?`.

## 8. Arbitrage final (E essentiel · A avancé · X écarté)

| Fonction | Classe | Correction |
|---|---|---|
| Saisie partout, analyseur FR/EN (« 10 h »), puces, chaîne, `#projet`, Nouveau projet, Quand/Échéance, priorité, collage + aperçu + titre de note (M9) + Coller encore, doublons, Annuler | E | — |
| Capture Siri rangée comme comprise (A1, M6) ; rappel sans jour pose le jour | E | spec 2 §3.4 : tout dans la Boîte |
| Rangement par le Copilote | E s'il est disponible | — |
| À trier en un geste, sélecteur de projet, check-list, notes, En réserve, recherche, à-faire convertis | E | — |
| Étiquettes, durée, récurrence, rappel par la phrase, projet suggéré, couleur, icône, sous-tâches, en attente de, confidentielle, filtres, tri, vues, Derniers gestes, sélection multiple | A | « Après… » fondu dans En attente de… |
| Captures hors ligne | E, invisible | autres gestes hors ligne X v1 |
| Glisser-déposer | E bureau, A iPhone | spec 3 : direct iPhone |
| Ligne de progression « faites sur objectif » | **E** | spec 3/5a : objectif replié, « 4/6 » |
| Essentiel, Prévu, Ce soir, obligations ERP mêlées, Suivi des relances | E | bandeau agenda fondu |
| **Proposé pour aujourd'hui + Garder ces N** = plan du jour | **E** | A11 ; plus de dialogue (spec 3) |
| À revoir replié + lot « Tout en réserve » | E | spec 3 : un choix par ligne |
| Retour d'absence en une carte | **E** | B1 |
| Alléger ma journée, sans report | **E** (⋯, message de 15 h) | M7 |
| « Le reste → lun. 23 » ; un constat au bilan | E | spec 3 : n + 2 ; M4 |
| Agenda 4 vues, blocs, rappels posés, visites et poses à leur heure | E | M8 ; spec 3 : journée entière |
| 3 jours, n° de semaine, jours travaillés seuls, échéances dans l'agenda, rappel avant bloc, agenda externe ICS | A | M8 |
| Auto-planification, déplacer un événement ERP, rappel de lieu, boutons de notification iOS | X | spec 3 |
| Projets : ordre manuel, priorité demandée et en puce, statuts, À planifier, 12 sur 20, santé, négligé, revue, terminer | E | M3 |
| Constat de projets ; vues Tableau / Chronologie | A | spec 4 : E |
| Groupe, Trier par priorité, dates d'étape, jalons, décaler, burn-up, projet de la semaine, modèles, dupliquer, archive | A | — |
| Plusieurs prérequis, Gantt, tableau par statut, statut couleur, plafond, OKR, modèles fournis | X | spec 4 |
| Objectif déclaré appliqué aussitôt, propositions +1/−1, Garder ce rythme, 4 faits | E | A2 |
| Sans objectif, jours courts, liste des constats, repère P60 | A | — |
| Points, badges, séries ; P60 objectif ou borne ; heures imposées | X | spec 5a |
| Copilote à 1 geste + 4 demandes prêtes | **E** | A12 ; spec 7 r1 : A |
| Boutons « … avec le Copilote » (Proposé, À trier, fiche, Mon rythme) | A | — |
| Liens ERP lead, client, devis, posés depuis la fiche ouverte | E | A3 |
| ✓+ sur les fiches ERP, suggestions devis accepté / chantier réceptionné ou annulé | E | — |
| Visite validée, suggestions société, Ailleurs dans l'ERP | A | — |
| Chatter, Ma file, visites liées, autres suggestions | X | spec 6a |
| Pastille, notifications, carte Mon iPhone au 1er collage, accueil, carte cockpit, flux, Siri, tuile, export, tout effacer | E | M5 |
| « Installer le raccourci », raccourci de manifeste « Tâches » | A | — |

**Replié davantage** (R7 §1, règle 12) : constat, vues iPhone, minutes, plan tenu, 7 filtres, heure et rappel, glisser
iPhone, phrase de santé. **Déplié** : objectif, Proposé, Copilote, priorité des projets, « Le reste → lun. 23 ».

## 9. Composants (`features/taches/ui/` ; vers `ui/`, unité deploy `docs/ownership.yml:805`, au 2e usage)

| Composant | Réutilise | Accessibilité · acceptation |
|---|---|---|
| `LigneTache` | `useSwipeReveal` recopié (`ui/datatable/DataTable.jsx:183`), `ContextMenu` | balayage = item de menu (WCAG 2.5.7) ; ligne gardée jusqu'au rechargement |
| `CaseRonde`, `Etoile` | `Checkbox` (`ui/Checkbox.jsx:16`, 18 px) dans 44 px | Espace / `*` ; < 0,1 s, retour arrière si échec ; 4e ★ refusée |
| `SelecteurQuand`, `ChampSaisie` | `DatePicker`, `TimePicker`, `Segmented`, `useDraftAutosave` | `radiogroup` ; puces annoncées ; annexe A spec 2 + « 10 h » ; texte jamais perdu |
| `FeuilleACrans` | `Sheet` (`ui/Sheet.jsx:15`, sans crans) | poignée = bouton ; brouillon gardé |
| `GrilleAgenda`, `Tableau` | `@dnd-kit/core`, `dndA11y.js`, `kanbanA11y.js` | toucher puis créneau ; « Déplacer vers… » |
| `AnneauProgression`, `CarteDuMoment`, `SelecteurProjet`, `ApercuListe` | SVG, `Card`, `Combobox`, `Checkbox` | jamais un % seul ; une carte ; « + Nouveau projet » fixe ; même rendu que `capture_apercu` |

## 10. Incohérences entre specs et résolution

| Incohérence | Résolution |
|---|---|
| « Ma journée » ; `g t` pris ; « coach » ; routes `/taches/bilan`, `?coach=1` / `?ouvrir=plan` | Aujourd'hui ; `g j` ; Copilote ; §2 |
| plan en dialogue (3) et Proposé (A11) ; « Tout au prochain jour ouvré » comptait des reports | Garder ces N ; Alléger ma journée |
| capture datée dans la Boîte (2) / A1 ; pastille sans Proposé (6b) ; ERP en journée entière (3) | rangée comme comprise ; pastille corrigée ; heure réelle |
| demain J+1 ou jour ouvré ; trois annulations ; glisser iPhone 150 ms / mode réorganiser | J+1 ; `GesteAnnulable` (A7) ; mode Réorganiser |
| `heure_prevue`/`heure_debut` ; « étapes » triple ; À décider, Un jour, Plus tard, Corbeille, Tâche privée, attend, importante, relance | `heure_debut` ; §3 |

## 11. Auto-évaluation (refaite)

Heuristiques : état 2 · monde réel 1 (Prévu/Proposé à apprendre) · contrôle 2 · cohérence 2 · prévention 1 (dictée mal
rangée possible) · reconnaître 1 (`#`, balayages, appui long, doublés) · efficacité 2 · minimalisme 1 (le soir 4
sections + 4 repliés) · erreurs 2 · aide 1 (pas de `?` iPhone) = **15/20**, note d'auteur, indulgente.
Parcours cognitif : retour de congé oui partout ; 15 h sans notification **non** à « voit l'action » (Alléger sous ⋯) ;
notes Apple oui, coût iOS ; parcours 1 **non** pour `#` tapé. 20 règles : 18 oui. WCAG, hauteurs : non mesurés.
**Non résolu** : copier-coller iOS ; Siri prêt = geste de Reda ; projets sans rétroplanning ; Copilote iPhone à vérifier.

## Choix par défaut et objection

« Prévu » évite de répéter le nom de l'écran ; « Message de 15 h » suit l'heure réglée. Objection : aucune.

## Révision 2 : ce qui a changé

1. Aujourd'hui : ordre écrit, « 1 sur 5 », Prévu, Proposé + « Garder ces N » = plan du jour (A11, M1, M2).
2. Retour d'absence en une carte (B1) ; « Alléger ma journée » (M7) : aucun report compté.
3. Priorité du projet demandée, en puce (M3) ; un constat au bilan (M4).
4. Mon iPhone au 1er collage (M5) ; capture rangée comme comprise (M6) ; titre de note = projet (M9).
5. Agenda : ERP à l'heure, ICS externe AVANCÉ (M8) ; « Chercher dans mes tâches » (M11).
6. À revoir, En réserve, Message de 15 h, Suivant, En attente de… (M10) ; Copilote à 1 geste (A12).
7. Pastille corrigée ; parcours 13-15 ; note refaite 15/20.
