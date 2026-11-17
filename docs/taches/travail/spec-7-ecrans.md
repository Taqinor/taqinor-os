# Spec 7 — L'ensemble : navigation, vocabulaire, écrans (`features/taches`)

Fait tenir les specs 2, 3, 4, 5a, 5b, 6a, 6b dans un seul produit. Loi : `recherche-7-simplicite.md` (« R7 règle n »).
Chemins front relatifs à `frontend/src/`. Les noms d'API et de code des specs restent ; seuls les MOTS montrés changent.

## 1. Modèle mental (le test)

1. « Je note tout ici, d'un geste ; ce qui n'a pas encore de place attend dans **À trier**. »
2. « Chaque matin je fais mon **plan du jour** : ce que je fais aujourd'hui, et mon **essentiel**. »
3. « **Aujourd'hui** me montre tout ce que j'ai à faire, ce que l'ERP attend de moi compris. »
4. « Le reste vit dans ses **projets** ; l'**agenda** me montre quand. »
5. « Le soir je fais le **bilan**, le dernier jour de la semaine la **revue** ; le **Copilote** m'aide à décider et à garder mon rythme. »

Une fonction qui ne sert aucune phrase est AVANCÉ (étiquettes, vues enregistrées, modèles, avancement détaillé, domaines, constats).

## 2. Navigation

**Barre du bas iPhone** (`BottomTabBar.jsx:33-48` : 5 onglets, « Apps » en prend un ; ≤ 4 sections → toutes directes, pas de « Plus »).
`nav.items` de Tâches = exactement 4, dans cet ordre (le 1er est la porte du module, convention `crm/module.config.jsx:88-92`) :

| Onglet | Route | Pastille |
|---|---|---|
| Aujourd'hui | `/taches/aujourdhui` (`/taches` y redirige, requête gardée) | — |
| À trier | `/taches/a-trier` | nombre à trier (masqué à 0) |
| Projets | `/taches/projets`, `/taches/projets/:id` | — |
| Agenda | `/taches/agenda?vue=jour\|semaine\|mois\|a-venir` | — |

Le bureau montre les mêmes 4 entrées dans la barre latérale (même source : `ActiveAppContext.jsx:153-158`).
**Le « Plus » unique** : bouton ⋯ dans la ligne de titre de chaque écran Tâches (pas dans l'en-tête global, trop serré sur
iPhone — spec 6a §9 d). Contenu : d'abord 1 à 3 actions de l'écran, puis toujours : Revue de la semaine · Mon rythme ·
Supprimées récemment · Réglages. À côté du ⋯ : la loupe (Recherche). **Ajout** : bouton flottant « Ajouter une tâche » sur
les 4 onglets iPhone (`ui/FloatingActionButton.jsx`, mobile seul) ; bureau : champ en tête de liste + `n`.
**Fiche** : `?tache=<id>` sur n'importe quel écran Tâches (feuille du bas iPhone, panneau droit bureau). **Rituels** :
`/taches/aujourdhui?ouvrir=plan|bilan`. Autres routes : `/taches/revue`, `/taches/rythme`, `/taches/recherche`,
`/taches/supprimees`, `/taches/reglages[/iphone|/notifications|/vie-privee|/donnees]`, `/taches/projets/archive|modeles`.
Écran d'ouverture : Aujourd'hui (l'icône, une fois « En faire mon accueil » fait : 0 geste).

**Fonction → où → gestes depuis Aujourd'hui (iPhone)**

| Fonction | Où | Gestes |
|---|---|---|
| Ajouter, coller une liste, dicter | bouton flottant → feuille de saisie | 1 |
| Cocher · Reporter | case · balayage gauche (ou fiche → Reporter) | 1 · 1 (2) |
| Fiche (notes, check-list, Quand, Échéance, Projet, Priorité) | toucher la ligne | 1 |
| Heure, rappel | fiche → Quand → Heure / Rappel | 3 |
| Répéter, étiquettes, durée, en attente de, après…, jalon, lié à, confidentielle, découper | fiche → Plus → champ | 3 |
| Déplacer · Mettre en attente · Essentiel · Sélectionner · Réorganiser | appui long → choix | 2 |
| À trier, suggestions de l'ERP, convertir les à-faire | onglet À trier | 1 |
| Projets · un projet · Un jour · En pause | onglet → ligne | 1 · 2 |
| Planifier le projet | Projets → projet → bandeau ou ⋯ | 3 |
| Vue Tableau / Chronologie, avancement détaillé, décaler les dates, modèle, terminer, archiver | Projets → projet → ⋯ → choix | **4** |
| Archive, Modèles | Projets → ⋯ → choix | 3 |
| Agenda, placer à une heure | onglet ; À placer → tâche → créneau | 1 ; 3 |
| Plan du jour · Bilan du soir | bandeau ou ⋯ (ou notification) | 1-2 |
| Planifier avec le Copilote | ⋯ → bouton (aussi dans le plan du jour) | 2 |
| Recherche · filtres · vues enregistrées | loupe · → Filtres · → Enregistrer | 1 · 2 · 3 |
| Revue de la semaine · Mon rythme · Supprimées récemment | ⋯ → choix | 2 |
| Mode du rythme · Ce que j'ai remarqué | ⋯ → Mon rythme → choix / « Détail » | 3 |
| Congés, jours courts, temps disponible | ⋯ → Mon rythme → Mes jours → champ (ou le dire au Copilote : 1 + phrase) | **4** |
| Notifications, Mon iPhone, Vie privée, L'ERP me suggère | ⋯ → Réglages → rubrique | 3 |
| Exporter · Tout effacer | ⋯ → Réglages → Mes données → bouton | **4** |
| Projet à l'arrêt après N jours, rappel avant chaque bloc | ⋯ → Réglages → Avancé → champ | **4** |

Les **4** : réglages rares d'un seul endroit (R7 règle 3 vise ≤ 2 depuis leur écran : tenu) ; « Tout effacer » est
irréversible, l'éloigner est voulu ; les vues d'un projet supposent un projet choisi.

## 3. Vocabulaire fermé (écrans, notifications, Copilote, tuile, flux iPhone)

| Terme | Définition | Interdits |
|---|---|---|
| Tâches | l'app (tuile, nav, manifeste) | to-do, todo |
| **Aujourd'hui** | l'écran du jour (« Ma journée » existe déjà : `installations/module.config.jsx:81`, `visites/module.config.jsx:51`) | Ma journée, Mon jour, Today (« Aujourd'hui » de Publicité, `adsengine/module.config.jsx:102`, vit dans une autre app) |
| À trier | reçu, pas encore rangé (sans projet ni jour) | boîte de réception, inbox, non classées |
| Projet · Étape · Jalon | un résultat à atteindre · une partie d'un projet (la `Section`) · une tâche-repère datée | section, phase, domaine (montré « Groupe »), milestone |
| Check-list · point | cases dans une tâche · une case | étapes, sous-liste |
| Sous-tâche | tâche sous une tâche (« Découper ») | étape |
| Quand | le jour prévu ; puce « jeu. 19 » | planifiée le, date d'exécution |
| Échéance | date limite ; puce « échéance ven. 20 » | deadline, date limite, due |
| Demain | toujours J+1 ; un report vers un autre jour porte sa date (« lun. 23 ») | — |
| Reporter | déplacer une tâche à plus tard (défaut : prochain jour travaillé) | décaler, repousser, replanifier, remettre |
| Choisir un jour | donner n'importe quel jour | replanifier |
| Décaler les dates | tout un projet de N jours | reporter le projet |
| Un jour | sans jour, à garder (`quelque_jour`) | plus tard, peut-être, someday |
| Passer | quitter un rituel ou une étape sans rien changer | plus tard, ignorer, sauter |
| Pas maintenant | refuser une proposition, qui reviendra | non merci |
| Essentiel · essentielle | 1 à 3 tâches choisies au plan du jour | important(e), top, focus |
| Priorité haute / moyenne / basse | l'échelle unique | urgent, P1 (accepté à la frappe seulement) |
| À décider | prévue un jour passé, reportée 3 fois, ou échéance proche sans jour | en retard, à trancher, overdue |
| Abandonner · abandonnée | ne plus faire (statut `annule`, gardée) | annuler (réservé à l'annulation d'un geste) |
| Annuler | défaire le dernier geste | — |
| Supprimer · Supprimées récemment | retirer (30 jours pour restaurer) | corbeille (celle de l'ERP est commune) |
| En attente de… | attend quelqu'un ou quelque chose | bloquée |
| Après… | ne commence qu'après une autre tâche (`bloquee_par`) | attend, dépend de, bloquée |
| Plan du jour · Faire le plan | le rituel du matin | planning, routine du matin |
| Bilan du soir · Faire le bilan | le rituel du soir | clôture, clore, shutdown |
| Revue de la semaine | le rituel hebdomadaire, remplace le bilan ce jour-là | bilan hebdo, rétrospective |
| Planifier le projet | les 2 minutes guidées d'un projet neuf ; « À planifier » = pas encore fait | phase de planification, cadrage |
| Projet de la semaine | un projet mis en avant pour 7 jours | focus |
| Copilote | l'assistant de l'ERP ; dans Tâches il conseille (`features/ia/CopilotPanel.jsx:141`) | coach, IA, assistant, agent, bot |
| Mon rythme · objectif du jour | l'écran · le nombre de tâches visé | palier, bloc, karma, zone, score |
| En faire plus · Garder ce rythme · Sans objectif | les 3 modes (`pousser`/`tenir`/`libre`) | pousser, tenir, libre, intensif |
| Plan tenu | faites parmi celles prévues au plan | taux de réussite |
| Objectif atteint | compte ≥ objectif | journée réussie, ratée, échec, série |
| Durée · temps disponible | estimation d'une tâche · minutes de travail par jour | estimation, effort, capacité, charge |
| Rappel | alarme posée par lui | alerte, alarme |
| Point de la journée | l'unique notification de journée | relance (mot du CRM : « Suivi des relances », `crm/module.config.jsx:109`) |
| Activité ERP · Lié à | une activité de l'ERP · le lien d'une tâche vers une fiche | tâche ERP |
| Confidentielle | jamais montrée au Copilote, titre masqué hors de l'app | privée (tout est privé), secrète |
| Faites | tâches cochées | terminées, logbook |

Dates relatives (« Demain », « lun. 23 »), durées « 25 min », jours « travaillés » (jamais « ouvrés » à l'écran).

## 4. Les écrans

Règles communes : un seul bouton plein (iPhone : le bouton flottant ; ailleurs celui nommé) ; une section vide n'est
pas affichée ; **chargement** = squelette (> 1 s), jamais sur une liste déjà là ; **erreur** = la liste reste +
« Pas à jour — 09:02 · Réessayer » ; **hors ligne** = dernier état + « Hors ligne · synchro à 09:02 », les ajouts partent
en file (spec 6b §8), les autres gestes grisés ; **vide** = une phrase + un bouton.

| Écran | Action principale | Visible d'emblée | Replié (geste) | Vide | iPhone ≠ bureau |
|---|---|---|---|---|---|
| Aujourd'hui | Ajouter | anneau « 4/6 · essentiel 1/2 · plan 3/5 » ; bandeau « Faire le plan » (avant plan) ; Essentiel ; Aujourd'hui (activités ERP, visites, interventions, ligne « Suivi des relances : 5 » ; heures fixes en tête) ; Ce soir | À décider (n) ; En attente (n) ; Faites (n) ; Ailleurs dans l'ERP ; détail de l'anneau (temps prévu / disponible, objectif) : toucher | « Rien de prévu aujourd'hui. » + Faire le plan (1re fois : Coller mes listes) | bureau : colonne droite = agenda du jour (glisser vers une heure) ; fiche à la place |
| Saisie | Ajouter (Retour) | champ, puces lues (×), barre Quand · Projet · Priorité | ⋯ : coller, en faire une seule tâche, étiquette, durée | — | iPhone feuille + clavier ; bureau champ en ligne, `c t` = dialogue |
| Aperçu de liste | Créer N tâches | lignes cochables, puces, « déjà dans X », projet commun | Ranger par projet (Copilote) ; une ligne → éditer | « Aucune ligne lisible. » | identique |
| Fiche | Fait | titre, puces Quand · Échéance · Projet · Priorité, notes, check-list ; Reporter | Plus (champs AVANCÉ) ; Découper / Planifier avec le Copilote ; Supprimer | — | feuille à 2 crans ; panneau droit |
| À trier | — (tri par ligne) | Suggéré par l'ERP ; lignes avec Aujourd'hui · Demain · Projet… · ⋯ ; bandeau « 7 à-faire d'Activités · Tout convertir » | ⋯ : Un jour, Garder sans projet, Supprimer ; Ranger avec le Copilote ; trier une par une | « Rien à trier. » + Voir mes projets | bureau : boutons au survol/focus |
| Agenda | Ajouter (jour courant hérité) | Segmenté Jour · Semaine · Mois · À venir, ← Aujourd'hui → | À placer (n) ; n° de semaine, jours travaillés seuls, échéances (⋯) | « Rien ce jour-là. » | iPhone : Jour, Semaine = 7 lignes, placer = toucher puis créneau ; bureau : grille horaire, glisser, redimensionner |
| Projets | Ajouter | projets actifs (pastille, nom, « 12 sur 20 », icône à surveiller, « À planifier ») ; Nouveau projet ; Un jour (n) | En pause (n) ; groupes ; ⋯ : Archive, Modèles, Trier par priorité | « Aucun projet. Colle tes listes : je les range. » | bureau : colonne des projets + projet ouvert à droite (déposer une tâche sur un projet = déplacer) |
| Un projet | Ajouter (projet hérité) | en-tête (nom, « fini quand… », échéance, 12 sur 20, phrase de santé, prochain jalon) ; étapes ; ajout par étape | Faites (n) ; ⋯ : vue Tableau/Chronologie, avancement détaillé, Décaler, Planifier, Modèle, Dupliquer, Pause, Terminer, Supprimer | « Planifier le projet (2 min) » + Passer | bureau : choix de vue visible |
| Planifier le projet | Suivant / Terminer | 1 question par écran : fini quand… · échéance (puces, avance seules) · premières actions | Étapes, jalons, risque (« Plus ») ; coller ; Proposer avec le Copilote | — | plein écran ; dialogue |
| Plan du jour | Valider le plan | 1 À décider (un choix par ligne) · 2 proposition cochée + temps « 3 h 10 pour 4 h » + objectif · 3 ★ essentiel 0-3 | une proposition de rythme au plus ; Planifier avec le Copilote | rien à décider : étape 1 sautée | dialogue à étapes, Passer visible |
| Bilan du soir | Valider | faites (lues), puis chaque reste : Demain · Choisir un jour · Un jour · Abandonner ; « Le reste → lun. 23 » ; ligne des 4 faits | un mot sur la journée (280 car.) | « Tout est fait. » + Valider | idem |
| Revue de la semaine | Terminer la revue | la semaine en 4 faits ; une carte par projet : Garder · Pause · Terminer · Passer, prochaine action ; Projet de la semaine | intention ; constat « 7 actifs, 3 ont avancé » ; Un jour | « Aucun projet actif. » | iPhone : une carte par écran |
| Mon rythme | — (choix du mode) | objectif du jour + source ; 3 modes ; 14 derniers jours (4 faits) ; proposition en cours | Détail : Ce que j'ai remarqué ; Mes jours ; « Mes tâches ont changé » ; Comprendre mon rythme ; Parler de mon rythme | « Je commence à te connaître : 3 jours sur 10. » | idem |
| Recherche | — | champ ; puces Faites aussi · Projet ▾ · Priorité haute | Filtres (Date passée, 7 jours, Sans date, En attente, Un jour, Avec échéance, Étiquette), tri, groupe, Enregistrer | « Rien pour « … ». » + Chercher aussi les faites | `/` au bureau |
| Réglages | — | Notifications · Mon iPhone · Vie privée · L'ERP me suggère · Mes données | Avancé | — | idem |
| Mon iPhone | l'étape en cours | 5 étapes (spec 6b §9), faites repliées | jetons : copier, régénérer, révoquer | — | sur bureau : « à faire depuis l'iPhone » |
| Supprimées récemment | Restaurer (par ligne) | liste 30 jours | Derniers gestes (7 jours) | « Rien de supprimé. » | idem |
| Carte cockpit « Tâches · Aujourd'hui » | Ouvrir Aujourd'hui | « 4 à faire · 2 faites », 3 lignes cochables (essentiel d'abord) | — | « Rien de prévu. » + Ouvrir | idem |

Vie privée (dans Réglages) porte les 8 vérités du socle §2.7 et §8 (fournisseur d'IA, confidentielle, qui peut lire,
société active, fuseau, journal masqué, note 👎 lisible) ; la ligne « Comprendre mon rythme » y renvoie vers Mon rythme.

## 5. Gestes et clavier

| Geste sur une ligne | Effet (partout) | Équivalent visible |
|---|---|---|
| Toucher la case | Fait / défait ; la ligne reste en place, barrée, jusqu'à la sortie de l'écran | — |
| Toucher le reste | ouvre la fiche | — |
| Balayage gauche | révèle Reporter (libellé = jour cible) + Choisir un jour ; complet = Reporter ; ligne estampillée « → lun. 23 » en place | fiche → Reporter |
| Balayage droite | révèle Fait ; complet = Fait | la case |
| Appui long | menu : Choisir un jour · Déplacer… · Essentiel · Mettre en attente · Priorité · Sélectionner · Réorganiser · Supprimer | fiche |
| Glisser | iPhone : seulement en mode Réorganiser (poignées + boutons ▲▼) ; bureau : direct (liste, agenda, projet) | ▲▼, `Alt+↑/↓` |

Toute écriture : toast « … · Annuler » (6 s, `lib/mutateWithUndo.js:39`) ; rien n'est perdu à son expiration : l'annulation
reste dans Derniers gestes (7 jours, serveur). Supprimer : jamais par balayage ; sans dialogue depuis un menu (réversible).

Clavier (bureau ; muet sous un dialogue : `useFocusedRecordShortcuts` + `scopeRef`, `providers/focusedRecordShortcuts.jsx:98-113`).
**Aucune touche seule ne fait disparaître une ligne** (règle maison, incident du 02/10) : la ligne reste, estampillée.

| Touche | Effet |
|---|---|
| `c t` (partout) · `g j` (partout) | Créer une tâche · aller à Aujourd'hui (`shortcut:'j'` du module ; `g t` est déjà le SAV, `shortcuts.js:35`) |
| `n` · `/` · `?` · Ctrl/⌘ K | ajouter ici · chercher · aide · palette |
| `j` / `k` · Entrée · Échap | ligne suivante/précédente (`LIST_SHORTCUTS`, `shortcuts.js:141`) · fiche · fermer |
| Espace · `d` (+ Entrée) · `m` · `x` · `h` | Fait · Quand (Entrée = Reporter au jour proposé) · Déplacer · Sélectionner · Heure |
| `Alt+↑/↓` · `Maj+↓` · Ctrl/⌘ Z | réordonner · bloc +15 min · annuler le dernier geste |
| Agenda : ← → · `t` | période · aujourd'hui |

Palette : Créer une tâche, Nouveau projet, Faire le plan, Faire le bilan, Aller à Aujourd'hui/À trier/Projets/Agenda,
Rechercher dans les tâches ; sur la ligne focalisée « Supprimer « titre » » et « Abandonner « titre » » avec un
dialogue qui nomme la tâche. Chaque menu affiche sa touche.

## 6. Parcours chiffrés (gestes hors texte ; cible R7 §3 sinon cible posée ici)

| # | Parcours | iPhone | Bureau | Cible | Écart |
|---|---|---|---|---|---|
| 1 | Demain dans un projet | + · « … demain #Polydesign » · Retour = 2 | `n` · texte · Entrée = 2 | 2 / 2 | via puces sans `#` : 4 (voir §11) |
| 2 | Dans un NOUVEAU projet | « #SiteWeb » → puce « Nouveau projet : SiteWeb » = 2 | 2 | 2 / 2 | — |
| 3 | Cocher | 1 | Espace 1 | 1 / 1 | — |
| 4 | Reporter à demain | balayage 1 (visible : 2) | bouton au survol 1 ; clavier `d` Entrée 2 | 1 / 1 | clavier +1 : règle maison |
| 5 | Choisir un autre jour | balayage · Choisir · jour = 3 | survol Quand · jour = 2 | 3 / 2 | — |
| 6 | Déplacer dans un projet | appui long · Déplacer · projet = 3 | `m` · Entrée = 2 | 3 / 2 | — |
| 7 | Plan du jour (3 à décider, 2 essentielles) | 1 + 3 + 2 + Valider = 7 | 7 | 2 + décisions + essentielles | — |
| 8 | Bilan du soir (n restes) | 1 + « Le reste → lun. 23 » + Valider = 3 | 3 | 3 | spec 3 : n + 2 |
| 9 | Vider À trier (3 vers projets, 2 datées) | 1 + 3×2 + 2×1 = 9 ; Copilote : 3 + corrections | 9 | ≤ 1 + 2 par tâche | — |
| 10 | Créer et planifier un projet | Projets · Nouveau projet · Créer · Suivant · puce · Terminer = 6 | 6 | 6 | spec 4 : 8 (planification ouverte d'office, puce qui avance seule) |
| 11 | Poser un rappel | ligne · Quand · Rappel « 15:00 » = 3 (ou « rappel 15h » tapé : 0) | 3 | 3 | — |
| 12 | Copilote, prioriser | ⋯ · Planifier avec le Copilote · Adopter ce plan = 3 | 3 | 3 | + choix d'À décider |

Estimation KLM (bureau, parcours 1) : 1,35 + 0,2 + 30 × 0,2 + 0,2 ≈ 7,75 s ≤ 8 s (R7 §11).
Aucun parcours au-dessus de sa cible hors le 4 au clavier (cause écrite).

## 7. Première utilisation

Aucune visite guidée. Ouverture : Aujourd'hui vide — « Note ce que tu as en tête : colle ou dicte tes listes, je les
range par projet. » + **Coller mes listes** (D-TCH-4). Les 3 premiers gestes : (1) coller ou dicter (micro du clavier) ;
(2) l'aperçu (titres « Maison : » = projets, sans IA) → **Ranger par projet** si le Copilote est disponible → corriger →
**Créer N tâches** ; (3) **Faire le plan** sur ce qui vient d'arriver. Rythme : muet ; l'objectif 5 n'apparaît que dans
le plan du jour, « valeur par défaut, pas encore calculée sur toi » ; aucune carte avant 10 jours travaillés.
Notifications : jamais demandées à la première ouverture (Mon iPhone, étape 1).

**Révélations : une par jour au plus, chacune une seule fois, au geste qui la rend utile.**

| Quand | Ce qui se montre |
|---|---|
| 1er plan validé (jour suivant) | carte « Ouvre Tâches d'un appui sur ton iPhone (2 min) » → Mon iPhone · Pas maintenant |
| 1re puce Projet choisie à la main | astuce « Tu peux aussi taper #Polydesign » |
| 3e report par la fiche | astuce « Balaie vers la gauche pour reporter » |
| À trier ≥ 5 | astuce « Ranger avec le Copilote » |
| 1er projet créé | Planifier le projet s'ouvre, Passer visible |
| dernier jour travaillé, ≥ 5 jours d'usage | Revue de la semaine à la place du bilan |
| 10e jour travaillé évalué | carte « J'ai 10 jours de toi : ta journée type est 3 tâches… » (spec 5a §3.10) |
| 1re tâche reportée 3 fois | elle arrive dans À décider avec « reportée 3 fois » |
| bureau, 5e ajout à la souris | « Astuce : `n` pour ajouter, `?` pour tout voir » |

## 8. Arbitrage final

| Fonction | Classe | Correction |
|---|---|---|
| Saisie partout, analyseur FR/EN, puces, chaîne, `#projet` + Nouveau projet, Quand/Échéance, priorité, collage + aperçu + groupes, doublons, Annuler | E | — |
| Rangement par le Copilote | E si disponible, sinon absent | — |
| À trier + tri en un geste, sélecteur de projet, check-list, notes, Un jour, recherche, conversion des à-faire | E | — |
| Étiquettes, durée, récurrence, rappel par la phrase, projet suggéré, trier une par une, couleur, icône, sous-tâches, en attente de, confidentielle, filtres, tri, groupe, vues, Derniers gestes, sélection multiple, dictée bureau | A | — |
| Captures hors ligne | E (invisible) | spec 3 l'écartait, spec 2 éditait `offlinesync` : file du module (spec 6b §8) ; autres gestes hors ligne X v1 |
| Glisser-déposer | E bureau, A iPhone (mode Réorganiser) | spec 3 : glisser direct iPhone |
| Essentiel, Aujourd'hui, Ce soir, activités ERP, visites/interventions en lignes, Suivi des relances | E | bandeau agenda (spec 3 E) fondu dans les lignes ; colonne au bureau |
| À décider (retards + reportées 3 fois + échéances proches) | E replié | 3 sections de la spec 3 → 1 |
| Anneau (faites, essentiel, plan tenu) | E ; temps et objectif repliés | spec 3 : minutes visibles |
| Tout au prochain jour ouvré (liste) | A | — |
| « Le reste → lun. 23 » dans le bilan | **E** | spec 3 : un choix par reste ; les reportées 3 fois en sont exclues |
| Agenda 4 vues, blocs, rappels posés | E | — |
| 3 jours, n° de semaine, jours travaillés seuls, échéances dans l'agenda, rappel avant bloc, nom du férié | A | — |
| Auto-planification, déplacer un événement ERP, maintenance société, rappel de lieu, boutons de notification iOS | X | raisons spec 3 |
| Projets : liste manuelle, priorité, statuts, « À planifier », couleur d'office, avancement « 12 sur 20 », santé, négligé, revue, terminer + Annuler | E | — |
| Constat « n actifs, n ont avancé » | **A** (revue) | spec 4 : E |
| Vues Tableau / Chronologie | A (⋯ sur iPhone) | spec 4 : sélecteur visible |
| Domaine (« Groupe »), Trier par priorité, étapes datées, jalons, après…, décaler, burn-up, projet de la semaine, modèles, dupliquer, archive | A | — |
| Plusieurs prérequis, Gantt, tableau par statut, statut couleur saisi, plafond de projets, OKR, modèles fournis, épingler | X | raisons spec 4 |
| Rythme : propositions de montée/baisse, Garder ce rythme, ligne des 4 faits | E | — |
| Objectif dit à la 1re ouverture | **A** (Mon rythme, Copilote) | spec 5a : carte au 1er jour |
| Sans objectif, jours courts, constats, repère P60 | A | — |
| Points, badges, séries ; P60 objectif ou borne ; heures imposées | X | raisons spec 5a |
| Copilote : boutons « … avec le Copilote » | A (⋯, plan, fiche, À trier, Mon rythme) | spec 5b : boutons sur les écrans |
| Lien ERP vers lead, client, devis, facture, chantier, ticket ; saisie pré-liée | E (posé tout seul depuis la fiche ouverte) ; choix à la main A | — |
| Compte de mes tâches liées (✓+ sur les fiches ERP) ; suggestions devis accepté, chantier réceptionné/annulé | E | — |
| 9 autres cibles, visite validée, suggestions société, Ailleurs dans l'ERP | A | — |
| Chatter, Ma file, visites/rendez-vous liés, autres suggestions | X | raisons spec 6a |
| Pastille, notifications (plan, point, bilan, rappel), accueil, carte cockpit, Mon iPhone, flux calendrier, Siri, tuile, export, tout effacer | E (Réglages pour les derniers) | — |
| Raccourci de manifeste « Tâches » | A | spec 6b : « Mes tâches » |

**Replié davantage que les specs** : constat de projets, sélecteur de vue (iPhone), minutes de l'anneau, 7 des 10 puces
de filtre, rappel et heure (dans Quand), objectif dit au 1er jour, glisser iPhone, phrase de santé (icône dans la liste,
phrase dans le projet), priorité sur la ligne (seulement haute, un drapeau). Raison commune : Hick (R7 §1) et ligne
≤ 4 informations (R7 règle 12) ; chacune reste à ≤ 2 gestes de son écran. **Déplié** : « Le reste → lun. 23 » (bilan
de n + 2 à 3 gestes, chaque ligne montre son jour avant Valider : aucun lot silencieux).

## 9. Composants (dans `features/taches/ui/`, propriété `taches` ; promotion vers `ui/` — unité deploy, `ownership.yml:805` — seulement au 2e usage)

| Composant | Rôle | Réutilise | Accessibilité | Acceptation |
|---|---|---|---|---|
| `LigneTache` | case, titre, ≤ 2 puces, balayages, appui long, estampille en place | patron `useSwipeReveal` (`ui/datatable/DataTable.jsx:183`, copié, pas extrait) ; `ContextMenu` ; `hapticTap` | balayage = action du menu (WCAG 2.5.1/2.5.7) ; rôle `listitem`, nom = titre + état ; annonce `aria-live` « Reportée à lun. 23 » | balayage complet ≥ 60 % = Reporter ; < 60 % révèle ; la ligne ne quitte la liste qu'au rechargement |
| `CaseRonde` | cocher | `Checkbox` Radix (`ui/Checkbox.jsx:16`, 18 px) dans une cible de 44 px ; `field-saved-pulse` | `role=checkbox`, Espace ; contraste 3:1 du contour ; mouvement réduit = 0 ms | coche < 0,1 s (optimiste), retour arrière + message si échec |
| `SelecteurQuand` | Aujourd'hui · Demain · Lun. · Un jour · Choisir… ; Heure ; Rappel | `DatePicker`, `TimePicker`, `ui/date-utils.js` | puces = `radiogroup` (`Segmented`) ; focus sur la 1re | « Demain » = J+1 ; jour non travaillé signalé, jamais refusé |
| `ChampSaisie` | texte + puces lues, × | `Input`, `useDraftAutosave`, `useKeyboardAwareScroll` | puces annoncées (`aria-live` poli), × = bouton nommé « Ne pas lire « demain » » | annexe A spec 2 rendue ; texte jamais perdu (hors ligne, erreur, fermeture) |
| `FeuilleACrans` | feuille du bas 50 % / 85 % | `Sheet` (`ui/Sheet.jsx:15`, sans crans) + CSS | poignée = bouton « Agrandir », Échap ; focus piégé | glisser vers le bas avec saisie → garde, jamais perte |
| `GrilleAgenda` | Jour/Semaine, blocs, À placer | `@dnd-kit/core` (Pointer 6, Touch 150/8, Keyboard), `dndA11y.js` | toucher-puis-créneau ; clavier `h`, `Maj+↓` ; annonces | chevauchements côte à côte ; aucun dépôt refusé |
| `Tableau` | colonnes = étapes | `usePanScroll`, `kanbanA11y.js` | « Déplacer vers… » au menu | ordre gardé après rechargement |
| `AnneauProgression` | faites / prévues | SVG sur jetons | `role=img` + texte « 4 sur 6 » | jamais un % seul ; 0 prévue → texte seul |
| `SelecteurProjet` | récents, recherche, Créer « X » | `Combobox` (activedescendant) | clavier complet | doublon refusé au champ |
| `ApercuListe` | aperçu de collage (écran ET carte Copilote) | `Checkbox`, puces | liste à cases | même rendu pour la carte `capture_apercu` |

## 10. Incohérences entre specs et résolution

| # | Incohérence | Résolution |
|---|---|---|
| 1 | « Ma journée » (3, 5b, 6a, 6b) = 2 écrans existants | « Aujourd'hui » |
| 2 | `/taches` (6a), `/taches/aujourdhui` (6b), `/taches?tache=` (3), `/taches/bilan` (6b), `/taches/taches/<id>` (5b §6) | routes du §2 ; la fiche passe par `?tache=` et `detail.tache_id` |
| 3 | `g t` (3) pris par le SAV | `g j` |
| 4 | « coach » (5b) ≠ « Copilote » du panneau | Copilote |
| 5 | À décider / à trancher / en retard / échéances proches (3) | une section « À décider » |
| 6 | bandeau agenda (3) et lignes d'obligations (6a) | lignes ; colonne au bureau |
| 7 | bandeau « à convertir » dans Ma journée (6a) et dans la Boîte (2) | À trier seul |
| 8 | « demain » = J+1 (2) ou prochain jour ouvré (3) | Demain = J+1 ; le report nomme son jour |
| 9 | toast 6 s (code) contre 8 s (R7) | 6 s maison + Derniers gestes |
| 10 | deux annulations (`GesteAnnulable` 2, `Annulation` 5b, `decaler/annuler` 4) | un seul bouton « Annuler », un seul modèle (au plan de le nommer) |
| 11 | glisser iPhone 150 ms (3) / mode réorganiser 300 ms (4) / appui long = menu (R7) | menu ; glisser en mode Réorganiser |
| 12 | `heure_prevue` (2) / `heure_debut` (3) | `heure_debut` (objection 4 de la spec 2), mot « Heure » |
| 13 | « étapes » = sections (4), points de check-list (2), sous-tâches (5a) | Étape = section seulement |
| 14 | « Plus tard » = passer (3, 4) et puce de date (4) | Passer · Un jour |
| 15 | « Corbeille » (2) / Supprimées récemment (socle) / Corbeille commune de l'ERP | Supprimer · Supprimées récemment |
| 16 | « Tâche privée » (5b) / « Tâche confidentielle » (6b) | Tâche confidentielle |
| 17 | « en attente de » (2) / « attend… » prérequis (4) | En attente de… · Après… |
| 18 | « Réglages › Rythme » (5a) / « Réglages rythme » (5b) | écran Mon rythme |
| 19 | revue des projets (4), message de semaine (5a), carte (5b) | un écran Revue de la semaine |
| 20 | dépôt sur un projet de la barre latérale (2) : barre générique | colonne des projets de l'écran Projets |
| 21 | « relance » (socle §5) = mot du CRM | Point de la journée |
| 22 | « 1 importante » (6b §3) | « 1 essentielle » |
| 23 | « Mes tâches » : manifeste (6b) et carte (6a) | « Tâches » · « Tâches · Aujourd'hui » |
| 24 | accueil : bouton permanent (6a P7, 6b §7) | carte unique + Mon iPhone étape 5 |
| 25 | filtre « En retard » (2) | « Date passée » |

## 11. Auto-évaluation (grille R7)

**Heuristiques** (0/1/2, produit entier) : 1 Visibilité 2 · 2 Monde réel 2 · 3 Contrôle 2 · 4 Cohérence 2 ·
5 Prévention 2 · 6 Reconnaître 1 · 7 Efficacité 2 · 8 Minimalisme 1 · 9 Erreurs 2 · 10 Aide 1 = **17/20**.
Écarts : (6) `#projet`, balayages et appui long sont invisibles — compensés par les puces, la fiche et une astuce, pas
supprimés ; (8) Aujourd'hui peut empiler 5 blocs visibles (anneau, bandeau, Essentiel, Aujourd'hui, Ce soir) quand tout
est rempli ; (10) pas d'aide sur iPhone hors astuces.

**Parcours cognitif** (Q1 but · Q2 voit l'action · Q3 la relie · Q4 voit le progrès) :
- Parcours 1 sur iPhone : Q1 oui · Q2 **non** pour `#` et « demain » écrits (puces : oui, mais 4 gestes) · Q3 oui · Q4 oui (puce lue en direct).
- Parcours 4 : balayage Q2 **non** au premier usage ; chemin visible fiche → Reporter : oui partout, 2 gestes = cible « 2 taps ».
- Parcours 6 : appui long Q2 **non** ; chemin visible fiche → Projet → choix : 3 = cible.

**Cibles** : a, b, c, d, e tenues sur iPhone par le chemin expert ; bureau c au clavier = 2 (cible 1, souris 1) ;
e = 0 seulement après « En faire mon accueil » (sinon Apps → Tâches = 2). **20 règles** : 18 oui ; non pour la règle 9 au
clavier et la règle 14 nuancée (le balayage a son équivalent dans la fiche, pas sur la ligne). WCAG 1.4.3, 2.1.1, 2.4.7,
2.5.7, 2.5.8 : conçus, non mesurés (rien n'est construit).

## Choix par défaut

1. « Aujourd'hui » plutôt qu'un nom neuf : le mot que dit tout le monde, sans collision dans le lanceur.
2. « À trier » plutôt que « Boîte de réception » : tient dans un onglet, dit quoi faire.
3. Le Copilote garde son nom : un seul panneau, un seul nom dans l'ERP.
4. Pas de « Plus » dans la barre du bas : 4 onglets directs ; le reste derrière le ⋯ de chaque écran.
5. Composants dans `features/taches/ui/` : aucun fichier `ui/` étranger touché pour la v1.

## Objections au socle

Le socle et D-TCH-2 disent « Ma journée » ; le nom n'a jamais été une décision du fondateur (spec 6a l'a laissé
ouvert) : l'écran s'appelle « Aujourd'hui », la route d'API `aujourdhui/` ne change pas, l'icône ouvre bien cet écran.
