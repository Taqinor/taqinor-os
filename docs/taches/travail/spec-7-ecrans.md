# Spec 7 — L'ensemble : navigation, vocabulaire, écrans (`features/taches`) — révision 3

Loi : R7 (`recherche-7-simplicite.md`), `arbitrages.md` A11-A16. Chemins : `frontend/src/`.

## 1. Modèle mental (le test)

1. « Je note tout d'un geste ; ce qui n'a pas de place attend dans **À trier**. »
2. « Le matin l'ERP **propose** ; je **garde** ce que je fais et choisis mon **essentiel**. »
3. « **Aujourd'hui** montre ce que j'ai à faire, ERP compris. »
4. « Le reste vit dans ses **projets** ; dans l'**agenda** je place ma semaine. »
5. « Le soir le **bilan**, en fin de semaine la **revue** ; le **Copilote** m'aide à décider et à tenir mon rythme. »

Hors de ces phrases → AVANCÉ.

## 2. Navigation

5 onglets dont « Apps », ≤ 4 sections toutes directes (`components/layout/BottomTabBar.jsx:33-48`) ; `nav.items` = 4, le 1er
= porte (`crm/module.config.jsx:83-88`), aussi dans la barre latérale (`lib/apps/ActiveAppContext.jsx:153-158`).

| Onglet | Route | Pastille d'onglet |
|---|---|---|
| Aujourd'hui | `/taches/aujourdhui` (`/taches` y mène) | — |
| À trier | `/taches/a-trier` | nombre, masqué à 0 (ajout à `BottomTabBar.jsx`, A8) |
| Projets | `/taches/projets[/:id]` | — |
| Agenda | `/taches/agenda?vue=jour\|semaine\|mois\|a-venir[&projet=]` | — |

**Seul « Plus »** : ⋯ du titre, touche affichée par item : actions de l'écran (Aujourd'hui : Alléger, Réorganiser,
Sélectionner, En faire mon accueil), puis Revue · Mon rythme · Supprimées récemment · Réglages ; loupe à côté.
**Copilote** : bouton global (`components/layout/Header.jsx:210-219`, iPhone non vérifié), 4 demandes : « Planifie ma
journée », « Aide-moi à prioriser », « Range ma liste », « Où j'en suis ? » ; sans clé ou hors ligne, une phrase.
**Ajouter** : bouton flottant (`ui/FloatingActionButton.jsx:6`), seul bouton plein. Fiche `?tache=<id>` ; notifications
→ Aujourd'hui (A15). **Pastille (N5)** : gardées encore ouvertes (Essentiel, Prévu, Ce soir), jamais Proposé ; peut valoir 0.

Comptes **atteindre / accomplir**, identiques au §7.

| Fonction | Où | Gestes depuis Aujourd'hui |
|---|---|---|
| Ajouter (texte, collage, dictée) | bouton flottant → Retour | 1 / 2 |
| Cocher · Reporter (ou ligne → Reporter) · Choisir un jour | case · balayage gauche · balayage → Choisir → jour | 1 / 1 · 1 / 1 (2 / 2) · 2 / 3 |
| Garder, essentiel · fiche | « Garder ces N », puis ★ · ligne | 1 / 1 (+1 par ★) · 1 / 1 |
| Heure, rappel | ligne → Quand → Heure ou Rappel → choix | 3 / 4 (rappel préréglé 3) |
| Répéter, étiquettes, durée, en attente de, jalon, lié à, confidentielle, découper | ligne → Plus → champ | 3 / 4 |
| Déplacer, en attente, priorité, essentiel | appui long → choix → valeur (ou ligne → champ) | 2 / 3 |
| Réorganiser · Sélectionner | ⋯ → choix | 2 / 2 + déplacements |
| Alléger ma journée | carte de 15 h (ou ⋯) → cocher k → Garder ces k | 1 (2) / 2 (3) + k |
| Copilote | bouton global → demande (→ Adopter) | 1 / 2 (3) |
| Lier une tâche à une activité ERP | appui long sur l'activité → choix → Ajouter | 2 / 3 |
| Trier, suggestions, à-faire à convertir | À trier → bouton (Projet… : + projet) | 1 / 2 (3) |
| Trier une par une | À trier → ⋯ → choix | 3 / 3 |
| Un projet · En réserve · En pause | Projets → ligne | 2 / 2 |
| Priorité d'un projet · Mettre en haut | Projets → puce → niveau · Projets → appui long → choix | 2 / 3 · 3 / 3 |
| Planifier le projet | Projets → projet → bandeau → priorité · Suivant · puce · Terminer | 3 / 7 |
| Vues, Voir dans l'agenda, burn-up, Décaler, Modèle, Dupliquer, Pause, Terminer, Supprimer · Archive, Modèles | Projets → projet → ⋯ · Projets → ⋯ | **4** / 4-5 · 3 / 3 |
| Placer à une heure | Agenda → tâche d'« À placer » → créneau | 2 / 3 |
| Planifier ma semaine | Agenda → Semaine → À placer → (tâche → jour) | 3 / 3 + 2 par tâche |
| Bilan du soir (d'hier jusqu'à 12 h) | carte ou notification → Tout reporter → Valider | 1 / 3 |
| Revue de la semaine | ⋯ → Revue (ou notification) | 2 / 2 + 1 par projet |
| Recherche, filtres, vues | loupe → Filtres → Enregistrer | 1 · 2 · 3 |
| Mon rythme · mode | toucher la progression · → mode | 1 · 2 |
| Congés, jours courts, temps disponible | progression → Mes jours → champ | 3 / 4 (Copilote 1) |
| Supprimées récemment · En faire mon accueil | ⋯ → choix (→ Restaurer) | 2 / 3 · 2 / 2 |
| Notifications, Mon iPhone, Vie privée, ERP me suggère | ⋯ → Réglages → rubrique | 3 / 4 |
| Exporter, Tout effacer, Avancé (messages sans délai, ICS) | ⋯ → Réglages → rubrique → bouton | **4** / 4-5 |

Les **4** : rares, à ≤ 2 gestes de leur écran (R7 r.3).

## 3. Vocabulaire fermé (écrans, notifications, Copilote, tuile, flux)

| Terme | Définition | Interdits |
|---|---|---|
| **Aujourd'hui** | l'écran du jour (A13) | Ma journée (`installations/module.config.jsx:81`, `visites/module.config.jsx:51`) |
| Prévu · Ce soir · Toute la journée | gardé pour aujourd'hui · le soir · visites et poses (sans heure, N4) | jour prévu |
| Proposé pour aujourd'hui · Garder ces N | prochaines tâches des projets, classées · les passer dans Prévu | plan proposé |
| Alléger ma journée | en garder une partie, le reste retourne aux projets sans report | — |
| À trier · Trier une par une | reçu sans projet ni jour · une carte par tâche | boîte de réception |
| À revoir | jour passé, reportée 3 fois, échéance proche sans jour | à décider, en retard |
| En réserve | gardée sans jour | un jour, plus tard |
| Projet · Étape · Jalon | résultat · partie d'un projet (`Section`) · tâche-repère | section, phase |
| Planifier le projet · À planifier · Planifier ma semaine | 2 minutes guidées · pas fait · placer dans les jours | — |
| Mettre en haut | premier des projets | épingler |
| Check-list · point · sous-tâche | cases d'une tâche · une case · tâche fille | étapes |
| Quand (« Quand je la fais ») | jour où il la fera, puce « jeu. 19 » | planifiée le |
| Échéance | date limite, puce « échéance ven. 20 » | deadline |
| Demain | toujours J+1, jamais un bouton de report | — |
| Reporter · Choisir un jour · Décaler les dates | au prochain jour travaillé, nommé (« Reporter à lun. 23 ») · tout jour · tout un projet | replanifier |
| Passer · Pas maintenant · Suivant · Fermer | quitter un rituel · refuser pour l'instant · carte suivante · fermer | plus tard |
| Essentiel(le) | 1 à 3 tâches (★) | important(e), focus |
| Priorité haute · moyenne · basse · aucune | l'échelle unique ; projet né par `#` = moyenne | urgent |
| Abandonner · Annuler · Supprimer | ne plus faire · défaire un geste · retirer 30 jours | corbeille |
| En attente de… | quelqu'un, quelque chose ou une tâche (puce « attend : Visite ») | après, bloquée |
| Bilan du soir · Revue de la semaine · Semaine courte | soir · hebdo, au lieu du bilan · revue sans chiffres (≥ 3 jours vides) | clôture |
| Reprise | progression du jour de retour (au lieu de « 0 sur 5 ») | — |
| Projet de la semaine | mis en avant 7 jours | focus |
| Copilote | l'assistant (`features/ia/CopilotPanel.jsx:141`) | coach, IA |
| Mon rythme · objectif du jour | l'écran · nombre visé (« 1 sur 5 ») | palier, score |
| Gardées faites | 2e ligne du bilan (« 4 des 5 gardées ») | plan tenu |
| En faire plus · Garder ce rythme · Sans objectif | modes `pousser`/`tenir`/`libre` | pousser, tenir |
| Objectif atteint | compte ≥ objectif | réussie/ratée, série |
| Durée · temps disponible | d'une tâche · minutes de travail par jour | capacité |
| Rappel | alarme qu'il pose ; « Encore 10 min · 1 h · Demain 9 h » | alerte |
| Message de 15 h | notification de journée (heure réglée) | relance (CRM, `crm/module.config.jsx:109`) |
| Activité ERP · Lié à | activité de l'ERP · lien vers une fiche | tâche ERP |
| Confidentielle | cachée au Copilote et hors de l'app | privée |

Jours « travaillés » (jamais « ouvrés »).

## 4. Les écrans

Partout : squelette après 1 s, jamais sur une liste affichée ; erreur : liste gardée, « Pas à jour · Réessayer » ;
relecture au retour du focus. **Carte du moment**, une seule : retour > brouillon (« Reprendre ») > bilan d'hier (avant
12 h) > « 1 sur 6 à 15 h · Alléger » > « Faire le bilan » > rythme > Mon iPhone > astuce. **Hors ligne (N11)** : ajouter,
cocher, reporter en file (6b §8) ; le reste grisé, « Possible une fois connecté » ; saisie gardée.

**Aujourd'hui, de haut en bas** : titre, loupe, ⋯ → (1) progression « 1 sur 5 · essentiel 0/2 » (« Reprise » au
retour ; toucher → Mon rythme) → (2) carte du moment → (3) Essentiel → (4) Toute la journée, puis **Prévu** : blocs à
leur heure, tâches et activités ERP mêlées (> 3 sans heure : une ligne repliable), « Suivi des relances : 5 » → (5) Ce
soir → (6) **Proposé pour aujourd'hui** jusqu'à l'objectif, 1re ligne expliquée (« échéance jeudi · projet prioritaire
Ventes »), « Garder ces N » (contour), surcharge à côté (« 5 h 10 pour 4 h »), « Voir tout » ; replié jusqu'au lendemain après « Alléger » → (7) repliés : À revoir (« Tout en réserve »), En attente,
Faites, Ailleurs dans l'ERP. Après « Garder » : « Touche ★ pour ton essentiel », focus sur « Prévu ». Jamais vide tant
qu'un projet actif a une tâche ouverte (A11).

| Écran | Action principale | Visible d'emblée | Replié | Vide · hors ligne |
|---|---|---|---|---|
| Aujourd'hui | Ajouter | ci-dessus | ci-dessus | sans projet : « Colle ou dicte tes listes » + Coller · file |
| Saisie, aperçu | Ajouter / Créer N | champ, puces (×), Quand · Projet · Priorité | Coller encore, Ranger | « Aucune ligne lisible » · file |
| Fiche | Fait | Quand · Échéance · Projet · Priorité, ★, notes, check-list, Reporter | Plus ; confier = activité ERP | — · saisie gardée |
| À trier | (par ligne) | Suggéré par l'ERP ; Aujourd'hui · Demain · Projet… · ⋯ | En réserve, une par une, Copilote | « Rien à trier » · file |
| Agenda | Ajouter (créneau vide = son heure) | 4 vues, ← Aujourd'hui →, Toute la journée, À placer (Semaine : + « Mes projets ») | affichage, « Férié » (nom v1.1) | « Rien ce jour-là » · lecture |
| Projets | Ajouter | puce de priorité, nom, 12 sur 20, à surveiller, À planifier ; Nouveau projet ; En réserve | En pause ; Archive, Modèles, Trier | « Aucun projet » + Coller · lecture |
| Un projet | Ajouter | nom + priorité ; « 12 sur 20 · échéance 20/12 » ; santé si signal ; étapes | Détails ; Faites ; ⋯ | « Planifier le projet » + Passer · lecture |
| Planifier le projet | Suivant | seul après Créer : priorité + fini quand… · échéance (1 sem → 3 mois, 6 sem ; avance seule) · actions + Copilote | étapes, jalons, risque | — · brouillon gardé |
| Bilan du soir | Valider | « 4 sur 5 », « 4 des 5 gardées » ; par reste : Reporter à lun. 23 · Choisir un jour · En réserve · Abandonner ; Tout reporter ; un constat | un mot | « Tout est fait » · choix gardés |
| Alléger | Garder ces k | lignes de Prévu, rien coché | — | — · grisé |
| Revue | Terminer → Planifier ma semaine | 4 faits (ou « Semaine courte, on reprend lundi ») ; par projet : Garder · Pause · Terminer · Suivant | intention, projet de la semaine | « Aucun projet actif » · grisé |
| Mon rythme | (mode) | aujourd'hui, 3 modes, 14 jours, proposition | constats, Mes jours, Comprendre mon rythme | « 3 jours sur 10 » · lecture |
| Recherche | — | champ ; Faites aussi · Projet ▾ · Priorité haute | 7 filtres, tri, Enregistrer | « Rien pour « … » » · dernière liste |
| Réglages, Mon iPhone | — · l'étape en cours | 5 rubriques · 5 étapes (6b §9) | Avancé · jetons | — · lecture |
| Supprimées récemment | Restaurer | 30 jours ; un projet = une ligne (projet + tâches) | Derniers gestes | « Rien de supprimé » · grisé |
| Copilote | la demande | 4 demandes | — | sans clé, hors ligne : une phrase |
| Carte cockpit | Ouvrir | « 1 sur 5 », 3 lignes | — | « Rien de gardé » · lecture |

Bureau : agenda du jour à droite, colonne des projets, glisser. iPhone : Semaine en 7 lignes ; bloc → Déplacer →
créneau. **Retour (B1)** : fin de congé ou ≥ 3 jours sans ouverture → « Tu reviens après 10 jours : 18 tâches
attendaient. » [Les remettre dans Proposé] [Les voir une par une]. **Supprimer le projet (N7)** : dialogue « … et ses 25
tâches ? » ; tâche restaurée seule → À trier. **Conflit (N8)** : « Modifiée sur ton autre appareil à 10:42 · Garder la
mienne · Prendre l'autre ». **Siri (N12)** : raccourci sans jeton, demandé à l'installation ; « Copier mon jeton » ;
« Installer » si `TACHES_RACCOURCI_SIRI_URL` (`deploy`, A8). Activité ERP cochée : close dans l'ERP, sans « Annuler ».
Récurrente : « Fait · prochaine jeu. 19 ».

## 5. Gestes et clavier

| Geste sur une ligne | Effet, partout | Équivalent visible |
|---|---|---|
| Toucher la case | Fait / défait ; la ligne reste, barrée, jusqu'à la sortie de l'écran | — |
| Toucher le reste | fiche | — |
| Balayage gauche | révèle « Reporter à lun. 23 » + Choisir un jour ; complet = Reporter, estampille en place | fiche ; Actions |
| Balayage droite | révèle Fait ; complet = Fait | case |
| Appui long | Choisir un jour · Déplacer… · Essentiel · En attente de… · Priorité · Lier une tâche (activité ERP) · Supprimer | Actions ; fiche |
| Glisser | iPhone : mode Réorganiser (▲▼, ▲ en tête d'étape = étape précédente) ; bureau : direct | ⋯ → Réorganiser, `Alt+↑/↓` |

Aucune touche seule ne fait disparaître une ligne (règle maison du 02/10). Clavier muet sous un dialogue
(`providers/focusedRecordShortcuts.jsx:98-113`) et (N1) après `g` ou `c` pendant le délai de séquence. Focus initial :
1re ligne ; `j`/`k` parcourent les lignes visibles, Proposé compris.

| Touche | Effet |
|---|---|
| `c t` · `g j` (partout) | Créer une tâche · Aujourd'hui (`shortcut:'j'`, `providers/shortcuts.js:69` ; `g t` = SAV, `:35`) |
| `n` · `/` · `?` · Ctrl/⌘ K | ajouter ici (contexte d'écran ; une puce tapée ne passe pas à la suivante) · chercher · aide · palette |
| `j` `k` · Entrée · Échap | ligne suivante/précédente (`shortcuts.js:141`) · fiche · fermer |
| Espace · `e` · `d` · `m` · `x` · `h` · `*` | Fait · renommer · Quand (Entrée = Reporter au jour nommé) · Déplacer · Sélectionner · Heure · Essentiel |
| `Alt+↑/↓` · `Maj+↓` · Ctrl/⌘ Z hors champ | réordonner · bloc +15 min · annuler |
| Agenda : ← → · `t` | période · aujourd'hui |

**N2** : `taches` au registre de l'aide (`providers/focusedRecordShortcuts.jsx:46`) ; palette : Créer une tâche, Chercher
dans mes tâches (non indexées, socle §2.4), Copilote et ses 4 demandes, Nouveau projet, Faire le bilan, les 4 onglets,
« Supprimer/Abandonner « titre » » (dialogue nommant) — fichiers `deploy`, A8.

## 6. Accessibilité (N10)

`role=status` annonce chaque geste (« Fait : Appeler Karim », « Reportée à lun. 23 », « 5 gardées », « 3 retournées
aux projets », « Annulé »). Toast « Annuler » 8 s (`duration`, `lib/toast.js:140`), en pause survolé ou focalisé ;
réglage « Messages sans délai » (WCAG 2.2.1). Chaque ligne a un bouton « Actions », visible au focus (Tab, VoiceOver),
qui ouvre le menu de l'appui long : rien n'exige balayage ni glisser (WCAG 2.5.1, 2.5.7). Cibles ≥ 44 px (case, ★, ×,
▲▼). Texte en rem (Dynamic Type d'une PWA : de mémoire). Contrastes 4,5:1 et 3:1 ; mouvement réduit.
Critères — Étant donné… alors : (1) lecteur d'écran, je coche → `role=status` dit « Fait : <titre> » ; (2) toast
focalisé, 8 s passent → il reste ; (3) réglage allumé → il reste jusqu'à fermeture ; (4) toute action de ligne au clavier
par Tab → Actions → item ; (5) texte à 130 %, 390 × 844 → 1re tâche d'Aujourd'hui visible sans défiler ; (6) axe-core :
0 violation par écran ; (7) toute cible ≥ 44 × 44 px CSS ; (8) après « Garder ces N », focus sur « Prévu ».

## 7. Parcours chiffrés (gestes hors texte)

| # | Parcours | iPhone | Bureau | Cible |
|---|---|---|---|---|
| 1 | Demain dans un projet | + · « … demain #Polydesign » · Retour = 2 | `n` · Entrée = 2 | 2 / 2 |
| 2 | Nouveau projet (moyenne) | « #SiteWeb » = 2 | 2 | 2 / 2 |
| 3 | Cocher | 1 | Espace 1 | 1 / 1 |
| 4 | Reporter | balayage 1 (ligne → Reporter 2) | survol 1 ; `d` Entrée 2 | 1 / 1 |
| 5 | Choisir un autre jour | balayage · Choisir · jour = 3 | survol 2 ; `d` · jour · Entrée 3 | 3 / 2 |
| 6 | Déplacer dans un projet | appui long · Déplacer · projet = 3 | `m` · Entrée = 2 | 3 / 2 |
| 7 | Garder sa journée, 2 essentielles | notification · Garder ces 5 · ★★ = 4 | 4 | 2 + ★ |
| 8 | Bilan du soir | notification · Tout reporter · Valider = 3 | 3 | 3 |
| 9 | Vider À trier (3 projets, 2 dates) | 1 + 3×2 + 2 = 9 ; Copilote 3 | 9 | 1 + 2 / tâche |
| 10 | Créer et planifier un projet | Projets · Nouveau · Créer · priorité · Suivant · puce · Terminer = 7 | 7 | 7 |
| 11 | Rappel | ligne · Quand · préréglé = 3 (heure précise 4, tapé 0) | 3 | 3 |
| 12 | Copilote, prioriser | bouton · demande · Adopter = 3 | Ctrl K · Entrée · Adopter = 3 | 3 |
| 13 | Retour de 10 jours de congé | ouvrir · Les remettre · Garder ces 5 = 3 | 3 | 3 |
| 14 | 1re ouverture, 4 notes Apple | 8 + 3 × 7 (Coller encore) + Créer = 30, dont 24 d'iOS | ≈ 3 / note | — |
| 15 | 15 h, 1 sur 6, alléger | notification · Alléger · 2 · Garder ces 2 = 5 | ⋯ · Alléger · 2 · Garder = 5 | 5 |
| 16 | **Planifier ma semaine**, 15 tâches | fin de Revue · bouton · 15 × (tâche · jour) = 31 (onglet : 33) | 15 glissers | 1 + 2 / tâche |
| 17 | 4 tâches à une heure | Agenda · 4 × (tâche · créneau) = 9 | 4 glissers | 1 + 2 / tâche |
| 18 | Clavier : 3 ajouts, 2 cochées, 2 reportées, 2 déplacées, Copilote | — | ≈ 19 touches (`g j`, `n`, `j`, Espace, `d`, `m`, Ctrl K) | — |
| 19 | Projet de 25 : ouvrir, réordonner 3, Tableau | 2 · 9 · 2 (mémorisée) | 2 · 6 · 2 | — |
| 20 | Brouillon · récurrente cochée à tort · projet supprimé à tort | 2 · 1 · 1 (Supprimées : 3) | idem | — |
| 21 | 4 jours absents, ven. 17 h | ouvrir · Les remettre · Garder ces 3 = 3 ; 18 h Semaine courte · Passer 1 | 4 | — |
| 22 | Deux appareils | coché ailleurs : relu au focus 0 ; conflit : Garder la mienne 1 | idem | — |

Cibles 1-6 : R7 §3. Au-dessus : le 4 au clavier (règle maison) ; le 14, par iOS.

## 8. Première utilisation

Pas de visite. Aujourd'hui sans projet : « Colle ou dicte tes listes. » + **Coller mes listes** (D-TCH-4) → aperçu
(1re ligne suivie de ≥ 2 lignes = « Nouveau projet : … » ; Coller encore) → **Créer N tâches** → carte Mon iPhone ; le
lendemain Proposé est rempli et la notification sonne (A15). Objectif 5 « valeur par défaut », aucune proposition de
rythme avant 10 jours. Une révélation par jour : `#`, balayage, Copilote, Planifier, Revue, « J'ai 10 jours de toi », `n`/`?`.

## 9. Arbitrage final (E essentiel · A avancé · X écarté)

| Fonction | Classe | Source |
|---|---|---|
| Saisie partout, analyseur FR/EN, puces, chaîne, `#projet`, Nouveau projet, Quand/Échéance, priorité, collage + aperçu + titre de note, doublons, Annuler | E | spec 2, M9 |
| Siri rangé comme compris, sans jeton ; rangement par le Copilote | E | A1, M6, N12 |
| À trier en un geste, sélecteur de projet, check-list, notes, En réserve, recherche, à-faire convertis | E | spec 2 |
| Trier une par une, étiquettes, durée, récurrence, rappel par la phrase, projet suggéré, couleur, icône, sous-tâches, en attente de, confidentielle, filtres, vues, Derniers gestes, sélection multiple | A | spec 2 |
| Ajouter, cocher, reporter hors ligne | **E** | N11 (spec 3 : X) |
| Glisser-déposer | E bureau, A iPhone | N10 |
| Progression sur objectif, Reprise ; Essentiel, Prévu, Ce soir, Toute la journée, activités ERP (lier une tâche), Suivi des relances | E | M2, N4, N9 |
| Proposé + Garder ces N + surcharge ; Alléger puis Proposé replié ; À revoir + Tout en réserve ; retour en une carte | E | A11, M7, N6, B1 |
| Bilan (4 sur 5, gardées faites, Tout reporter, un constat), bilan d'hier jusqu'à 12 h ; rappel « Encore 10 min… » | E | M2, M4, spec 3 |
| Agenda 4 vues, blocs, rappels posés, Planifier ma semaine | E | N3 |
| 3 jours, n° de semaine, jours travaillés seuls, échéances dans l'agenda, rappel avant bloc, nom du férié (v1.1), agenda externe ICS | A | M8 |
| Auto-planification, déplacer un événement ERP, rappel de lieu, boutons iOS | X | spec 3 |
| Projets : ordre manuel, Mettre en haut, priorité (moyenne par défaut, touchable), statuts, À planifier, 12 sur 20, santé, négligé, revue, terminer, supprimer (restauration en une ligne) | E | M3, N7 |
| Constat, Tableau / Chronologie mémorisées, Voir dans l'agenda, groupe, Trier par priorité, jalons, décaler, burn-up, projet de la semaine, modèles, dupliquer, archive, découpage Copilote | A | spec 4 |
| Plusieurs prérequis, Gantt, tableau par statut, statut couleur, plafond, OKR, modèles fournis | X | spec 4 |
| Objectif déclaré appliqué aussitôt, propositions +1/−1, Garder ce rythme, 4 faits, Semaine courte | E | A2, N9 |
| Sans objectif, jours courts, liste des constats, repère P60 | A | spec 5a |
| Points, badges, séries ; P60 objectif ou borne ; heures imposées | X | spec 5a |
| Copilote à 1 geste, 4 demandes, palette | E | A12, N2 |
| Boutons « … avec le Copilote » (Proposé, À trier, fiche, planification, Mon rythme) | A | — |
| Liens ERP lead, client, devis ; ✓+ ; suggestions devis accepté, chantier réceptionné ou annulé | E | A3 |
| Visite validée, suggestions société, Ailleurs dans l'ERP | A | spec 6a |
| Chatter, Ma file, visites liées, autres suggestions | X | spec 6a |
| Pastille, notifications, Mon iPhone au 1er collage, En faire mon accueil, carte cockpit, flux, Siri, tuile, export, tout effacer, conflit sans perte, §6 | E | N5, M5, N8, N10 |
| « Installer le raccourci », raccourci de manifeste, messages sans délai | A | — |

**Replié davantage** (R7 §1, règle 12) : constat, vues iPhone, minutes, 7 filtres, heure et rappel, glisser iPhone,
détails d'un projet, ★. **Déplié** : objectif, Proposé, Copilote, priorité des projets, Tout reporter, Planifier ma semaine.

## 10. Composants (`features/taches/ui/` ; vers `ui/`, unité deploy `docs/ownership.yml:805`, au 2e usage)

| Composant | Réutilise | Acceptation |
|---|---|---|
| `LigneTache` | `useSwipeReveal` recopié (`ui/datatable/DataTable.jsx:183`), `ContextMenu` | bouton Actions ; ligne gardée jusqu'au rechargement |
| `CaseRonde`, `Etoile` | `Checkbox` (`ui/Checkbox.jsx:16`, 18 px) dans 44 px | < 0,1 s, retour arrière si échec ; 4e ★ refusée |
| `SelecteurQuand`, `ChampSaisie` | `DatePicker`, `TimePicker`, `Segmented`, `useDraftAutosave` | annexe A spec 2 + « 10 h » ; brouillon signalé |
| `FeuilleACrans`, `CarteDuMoment`, `BandeauConflit` | `Sheet` (`ui/Sheet.jsx:15`), `Card`, `NextActionBanner` | ordre du §4 ; saisie conservée |
| `GrilleAgenda`, `VoletAPlacer`, `Tableau` | `@dnd-kit/core`, `dndA11y.js`, `kanbanA11y.js` | toucher puis créneau ou jour |
| `AnneauProgression`, `SelecteurProjet`, `ApercuListe` | SVG, `Combobox`, `Checkbox` | « + Nouveau projet » fixe ; même rendu que `capture_apercu` |

## 11. Incohérences entre specs et résolution

| Incohérence | Résolution |
|---|---|
| « Ma journée », `g t`, « coach », `/taches/bilan`, `?coach=1` ; plan en dialogue (3) | §2-§3 ; Garder ces N |
| « Tout au prochain jour ouvré » comptait des reports ; capture datée dans la Boîte (2) ; pastille avec Proposé | Alléger ; rangée comme comprise ; gardées seules |
| hors ligne « Ajouter désactivé » (2 §6), écritures X (3) ; 409 « par quelqu'un d'autre » (3) | file (N11) ; conflit sans perte (N8) |
| rappel dans la fiche (3) ; bandeau Planifier (4) ; visites « à l'heure » ; phrases 5a « prévues ou en retard », « 4 faites sur 6 » | Quand ; ouverte seule ; Toute la journée ; « 3 prévues · objectif 5 », « 4 sur 5 » |
| « Demain » au bilan ; trois annulations ; glisser 150 ms ; `heure_prevue` ; « étapes » triple | Reporter à lun. 23 ; `GesteAnnulable` (A7) ; Réorganiser ; `heure_debut` ; Étape = section |

## 12. Auto-évaluation

Heuristiques : 2 partout sauf monde réel 1 (Prévu/Proposé à apprendre), reconnaître 1 (`#`, balayages, appui long,
doublés), minimalisme 1 (le soir, 4 sections + 4 repliés), aide 1 (pas de `?` sur iPhone) = 16/20, note d'auteur.
Parcours cognitif : retour, 15 h, semaine : oui ; `#` tapé : non. §2, §4 et §7 recoupés. **Non résolu** : copier-coller
iOS ; Siri = geste de Reda ; pas de rétroplanning ; Copilote iPhone, Dynamic Type, question d'import non vérifiés ;
4 fichiers `deploy` à tracer. Choix par défaut : toast 8 s (R7) au lieu de 6 s maison ; tâche restaurée sans son projet
→ À trier. Objection au socle : aucune.

## Révision 3 : ce qui a changé

1. Clavier : `g`/`c` (N1), aide et palette (N2), `e`, Ctrl Z.
2. Planifier ma semaine (N3) ; Toute la journée (N4) ; pastille sur les gardées (N5).
3. Proposé replié après Alléger (N6) ; Supprimer le projet (N7) ; conflit sans perte (N8).
4. Semaine courte, Reprise, cartes (N9) ; §6 (N10).
5. Hors ligne étendu (N11) ; Siri sans jeton (N12) ; « 4 sur 5 » au bilan ; projet `#` = moyenne.
6. Orphelines placées, états par écran, comptes alignés, parcours 16-22.
