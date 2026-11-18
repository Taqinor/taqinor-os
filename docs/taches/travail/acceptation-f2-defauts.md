# Acceptation en direct de la fusion 2 — rapport de la mise au point (18/11/2026)

Rapport rendu par l'agent qui a écrit et joué `frontend/e2e/acceptation/tch.spec.js` sur la pile locale (arbre `dev-taches-f2` d'avant les corrections de la seconde relecture). Recopié tel quel.

## Rapport : acceptation en direct TCH, fusion F2 (TCH136-TCH140, TCH144)

Le dernier lancement complet donne **20 étapes PASS et 15 ROUGES sur 35**. Aucune étape rouge ne vient d'une erreur de la spec. Les 15 rouges se répartissent ainsi : 7 défauts de l'écran ou du serveur, 5 défauts du semis (`seed_taches_demo` ne reproduit pas SCENARIO.md) et 3 oracles du plan qui contredisent SCENARIO.md, la référence ou le semis. Je n'ai modifié aucun oracle, ni le code du produit, ni le semis, ni les tests existants.

### Branche et état
- Branche locale `lane/f2-acceptation`, tête `f04980ca90c4bb947faad96d5061f58c613acf70`.
- `git log --oneline dev-taches-f2..HEAD` :
  - `f04980ca90` Acceptation TCH — captures de relecture prises avant les oracles (projets, revue, agenda, recherche)
  - `b5cefb28b7` Acceptation TCH — mise au point en direct des six parcours (TCH136-TCH140, TCH144)
  - `e7de49b2ed` Acceptation TCH — spec écrite à la lecture, jamais jouée
- `git status --short` est vide. Les enregistrements `docs/audits/acceptation/TCH` et `docs/qa-explorer/captures` ont été nettoyés. Le lien `node_modules` et `playwright.cloud.config.mjs` sont ignorés par git.
- `npx eslint e2e/acceptation/tch.spec.js e2e/taches-acceptation.js` passe sans erreur.
- Fichiers livrés :
  - `/home/user/taqinor-os/.claude/worktrees/agent-a7bfb6c82ab821f0d/frontend/e2e/acceptation/tch.spec.js`
  - `/home/user/taqinor-os/.claude/worktrees/agent-a7bfb6c82ab821f0d/frontend/e2e/taches-acceptation.js` (semis et horloge, connexion `demo_taches` dans un contexte neuf, vues iPhone et bureau, doigt réel par CDP, captures).

### Dernier lancement complet
Il a été joué sur `b5cefb28b7` : **`15 failed, 21 passed (19.3m)`** (les 21 comprennent le projet `setup`).
- P139.3 y était tombé sur un incident de pile (`acc.sh horloge` : « pas de réponse de …/health/ en 90 s »).
- J'ai rejoué P138.1, P138.4, P139.1, P139.3 et P140.1 sur la tête finale `f04980ca90` : `4 failed, 2 passed (3.6m)`. Les rouges et leurs causes sont identiques.
- Entre les deux commits, seul l'ordre des captures change (et une capture Recherche est ajoutée). Aucun oracle ne bouge.

| Étape | Verdict | Cause |
|---|---|---|
| P136.1 | PASS | |
| P136.2 | ROUGE, défaut produit | défaut 1 |
| P136.3 | ROUGE, défaut produit | défaut 1 |
| P136.4 | PASS | |
| P136.5 | PASS | après remise à convertir (ERR-PLAN 3) |
| P136.6 | PASS | |
| P137.1 | ROUGE, semis | S1, S2 |
| P137.2 | PASS | |
| P137.3 | PASS | |
| P137.4 | ROUGE, semis/plan | S5 |
| P137.5 | PASS | |
| P137.6 | ROUGE, semis | S1 (le « 3 sur 5 · essentiel 1/2 » passe) |
| P137.7 | ROUGE, produit ou semis | défaut 6 |
| P137.8 | ROUGE, semis | S4 |
| P138.1 | ROUGE, ERR-PLAN | Benali « 12 sur 18 » passe, Site web non (ERR-PLAN 5) |
| P138.2 | PASS | |
| P138.3 | ROUGE, défaut produit | corps PASS, oracles 2 et 3 en échec (défaut 3) |
| P138.4 | ROUGE, ERR-PLAN | ERR-PLAN 6 |
| P139.1 | ROUGE, défaut produit | défaut 4 |
| P139.2 | PASS | |
| P139.3 | ROUGE, produit et semis | défaut 7 |
| P139.4 | ROUGE, semis | S3 |
| P139.5 | PASS | |
| P139.6 | PASS | |
| P139.7 | PASS | navigateur en `Africa/Casablanca` périmé : 10:00 enregistré tel quel |
| P140.1 à P140.4 | PASS | |
| P144.1 | ROUGE, défaut produit | défaut 5 |
| P144.2 | PASS | |
| P144.3 | ROUGE, défaut produit | défaut 2 |
| P144.4 | PASS | export : 21 modèles + `exporte_le` ; 0 ligne après Tout effacer |
| P144.5 | PASS | |
| P144.6 | PASS | |

### Défauts, du plus gênant au moins gênant
1. **ERR — P136.2 / P136.3** — attendu : « 4 listes → 4 « Nouveau projet » » puis « Créer » (plan TCH136, parcours 14). Constaté sur iPhone 390 × 844 : le pied de la feuille de saisie (« Coller encore », « Créer N tâches ») passe sous la barre d'onglets fixe. Playwright le dit : `<nav … class="bottom-tabbar bottom-tabbar--app"> subtree intercepts pointer events`. Personne ne peut créer ses listes collées sur iPhone. Preuve : `/opt/taches-cloud/captures/f2/preuves/P136.2-coller-encore-sous-barre-onglets.png`. Fichiers probables : `frontend/src/features/taches/ui/FeuilleACrans.jsx` (empilement et marge basse) face à la barre d'onglets de l'ERP. Les autres feuilles sont probablement touchées aussi.
2. **ERR — P144.3** — attendu : « 2 reportées » au clavier par `j d Entrée` (parcours 18, ≈ 27 touches). Constaté : `d` ouvre « Choisir un jour » avec une date vide et un bouton désactivé, et Entrée ne fait rien (`Error: tache:7982 reportée — Expected: true, Received: false`). Les 3 ajouts et les 2 cochées passent. Autre écart : la saisie se referme après chaque Entrée (`FeuilleSaisie.jsx`, `onFermer` après création), il faut retaper `n`. C'est compté et reste sous 27 touches. Fichier probable : `frontend/src/pages/taches/Aujourdhui.jsx` (`ChoisirJour`, action clavier `quand`).
3. **ERR — P138.3** — attendu : Supprimer, puis retour à la liste et toast Annuler. Constaté : l'écran reste sur `/taches/projets/<id>` avec « Ce projet n'existe plus. ». L'API renvoie `GET …/projets/123/vue/?vue=liste → 404`, suivi d'une `console.error`. Le dialogue « Supprimer « Stand partenaire » et ses 2 tâches ? », la ligne unique dans Supprimées récemment et Restaurer fonctionnent. Fichiers probables : `frontend/src/pages/taches/Projet.jsx` (`supprime` fait `navigate('/taches/projets')`) et `frontend/src/features/taches/ui/FeuilleACrans.jsx:62-69` (`history.back()` à la fermeture annule la navigation).
4. **ERR — P139.1** — attendu : jeu. 26 « 2 tâches · 2 h pour 4 h » (plan, et la maquette `agenda-semaine.html` l'affiche). Constaté en Semaine sur iPhone : « 2 tâches » sans la charge (`jeu.262 tâches09:00Réceptionner…`). L'API sert bien `capacite {minutes: 240}`. Preuve : `preuves/P139.1-semaine-sans-charge.png`. Fichier probable : `frontend/src/pages/taches/Agenda.jsx:343` (`SemaineListe`, `ag-sj-tete`).
5. **ERR — P144.1** — attendu : « Modifiée sur ton autre appareil à HH:MM · Garder la mienne · Prendre l'autre » (textes.md §2.2). Constaté : « Modifiée sur ton autre appareil », sans l'heure. La saisie est bien gardée et « Garder la mienne » écrit bien. Fichier probable : `frontend/src/features/taches/fiche/Fiche.jsx:289`, où `<BandeauConflit>` est rendu sans `heure`.
6. **ERR — P137.7** — attendu : « 4 des 5 gardées » (SCENARIO §3, 18:20). Constaté : `4 sur 5 · essentiel 2 sur 2` (correct), puis **« 4 des 6 gardées »**. La fiche de poste, passée au jeu. 26 à 14:10, reste comptée dans le plan du jour. À arbitrer entre le serveur (`apps/taches/selectors/journee.py`, `plan_lignes`) et le semis, qui fait ce geste par `trancher_tache(… 'jour' …)` au lieu de « Choisir un jour » (`seed_taches_demo.py:405-407`). Autre écart, hors oracle : le constat du bilan dit « 57 % de tes 51 tâches finies entre 10 h et 12 h. » alors que SCENARIO prévoit « Tu finis plus souvent ton essentiel… ».
7. **ERR — P139.3** — attendu : placer 4 tâches à une heure. Constaté : le volet « À placer » de la vue Jour n'offre que 3 tâches. L'API `agenda/?vue=jour` rend `mes_projets: []`, alors que `vue=semaine` en rend 4 groupes. SCENARIO §4 dit « À placer · 12 (Jour et Semaine) ». Les 3 poses réussissent (blocs visibles). Preuve : `preuves/P139.3-volet-3-taches.png`. Fichier probable : le sélecteur d'agenda (TCH59, « Mes projets en vue semaine »), plus le manque « À revoir » du semis (S1).

**Défauts du semis** (`backend/django_core/apps/taches/management/commands/seed_taches_demo.py` ; SCENARIO.md n'est pas reproduit). La lecture d'`aujourdhui/` à 08:30 le prouve : `carte_du_moment: bilan_hier`, `a_decider: []`, `obligations: []`, Proposé = [planning des poses « prévue hier », bureau de contrôle « prévue hier », rails].
- **S1** — « À revoir 2 » est vide. Le planning et le bureau de contrôle ne sont semés que « prévues lun. 23 », donc le serveur les met dans Proposé. La règle de textes.md l.43 (« reportée 3 fois ou prévue depuis plus de 7 jours ») ne les classe pas « À revoir ». Il faut trancher : semer des reports, ou corriger SCENARIO. Touche P137.1, P137.6 et P139.3.
- **S2** — la carte du moment est « Le bilan d'hier n'est pas fait… » au lieu de « 3 tâches proposées · Garder ces 3 » : le bilan du 23 n'est jamais semé.
- **S3** — ni « Visite technique à Témara » ni « Suivi des relances » ne sont semés (`toute_la_journee: []`). P139.4 est rouge.
- **S4** — `--absence` ne pose aucune dernière ouverture (`PlanJour.app_ouverte_le`), donc `services/journee.py::_est_un_retour` rend faux et la carte « Tu reviens après 10 jours… » n'apparaît pas (P137.8).
- **S5** — le semis rattache « Envoyer le devis révisé » à l'activité « Rappeler pour le devis » (`activite_origine`). « Lier une tâche » répond alors `409 {"code":"deja_lie","detail":"Cette activité a déjà sa tâche."}` (P137.4, rejoué aussi en direct sur l'API). Défaut produit secondaire : ce refus n'est annoncé qu'au lecteur d'écran, rien ne s'affiche à l'écran.

**ERR-PLAN** (le plan contredit SCENARIO.md, la référence ou le semis) :
1. P136.1 — le plan cite « Colle ou dicte tes listes. » ; textes.md donne « … : je les range par projet. ». J'ai joué la phrase de textes.md : PASS.
2. P136.2 — `premier-usage-1-apercu.html` ne montre que 2 listes, pas 4. Les 2 autres collages viennent de SCENARIO §2.
3. P136.5 — le semis convertit déjà l'à-faire « Envoyer la facture d'acompte ». L'étape rouvre l'activité et retire la tâche du semis avant de jouer le bandeau. Autre incohérence : la vraie conversion pose `due_date` en jour prévu (spec-2 l.144), alors que le semis et SCENARIO la mettent en échéance dans À trier.
4. P137.1 — le plan met « Relire le contrat de maintenance » dans Proposé ; SCENARIO §3 dit qu'il n'est **pas** proposé et nomme « Rédiger la fiche de poste ». J'ai joué SCENARIO.
5. P138.1 — Site web « À planifier » avec 4 tâches contredit `regles.md:657`, qui exige 0 tâche ouverte. Le produit suit la règle.
6. P138.4 — `--jour 2026-11-20` décale tout le scénario de −4 jours. Le produit affiche « 9 tâches en 2 jours ». Avec le semis par défaut et l'horloge à « 2026-11-20 17:40 », l'API rend exactement : « Du lun. 16 au ven. 20 : 21 tâches en 4 jours (précédente : 23). Objectif atteint 3 jours sur 4 · essentiel 3 sur 4. ». Écart de vocabulaire en plus : le plan dit « faites », textes.md §4.5 dit « tâches ».
7. P139.2 — le plan abrège en « 3 · 4 h pour 4 h ». J'ai joué la forme de textes.md, « 3 tâches · 4 h pour 4 h » : PASS.
8. P144.3 — les « ≈ 27 touches » comptent 4 touches de palette pour le Copilote, qui est en F3. Elles ne sont pas jouées.

Je n'ai relevé aucun cas « ERR-BASE-RAPIDE ? » : chaque rouge s'explique par le code ou le semis.

### Ce que je n'ai pas pu jouer
- La palette et le Copilote du parcours 18 (F3).
- La création de tâche de P137.4, bloquée par le 409 (S5).
- La pose d'une 4e tâche en P139.3, faute d'offre dans le volet.
- La suite de P144.3 (les déplacements par `j m Entrée`) n'est pas évaluée, puisque l'étape s'arrête sur le report.

### Ajustements de la spec, sans toucher aux oracles
- Le doigt passe par `Input.dispatchTouchEvent` (CDP) et la session n'est jamais détachée : la détacher repassait `navigator.onLine` à vrai au milieu du parcours hors ligne.
- La ligne visée est centrée avant le geste, sinon la barre d'onglets la recouvre.
- Le repli « Comprendre mon rythme » est ouvert avant l'interrupteur.
- « Lié à » se lit dans Fiche → Plus.
- La 4e adresse d'agenda est une IP publique, `https://1.1.1.1/…`, car la machine d'essai ne résout aucun nom.
- Le compte portail est créé par l'API de `acc_tch_admin`, avec un mot de passe d'essai posé en base sans « à changer ».

### Captures
`/opt/taches-cloud/captures/f2/` contient 96 PNG : 24 écrans × iPhone et bureau × clair et sombre.
- Écrans : `aujourdhui-vide`, `aujourdhui-matin`, `aujourdhui-15h`, `aujourdhui-retour`, `bilan`, `saisie`, `apercu-collage`, `a-trier`, `projets`, `projet`, `planifier-projet`, `supprimees`, `revue`, `agenda-jour`, `agenda-semaine`, `agenda-mois`, `planifier-semaine`, `mon-rythme`, `reglages`, `mes-donnees`, `recherche`, `fiche`, `fiche-plus`, `hors-ligne`.
- Le sombre est vérifié : `html[data-theme=dark]` est posé par `prefers-color-scheme`, que suit `design/theme.js`.
- `preuves/` contient 5 preuves de défauts.
- Limite : l'app défile dans un conteneur interne, donc la capture « pleine page » s'arrête à la hauteur de l'écran.
- À regarder en relecture visuelle : en sombre, l'icône du menu en haut à gauche est très peu contrastée.

La pile a été remise à l'heure réelle en fin de passe : `acc.sh etat` donne `django-8000 … reel`.
