# Vérifie ADCG — contre-visite de clôture du parcours PF3 « deploy / CI / gardes », 10/11/2026

Commande `loop audit` (10/11). L'audit de parcours PF3 (10/11, PR #1310) avait déposé ADCG1-100. Deux contre-visites le même
jour : mi-parcours à midi (48 cochées, PR #1331, qui a déposé ADCG101-102), puis clôture le soir (76 tâches cochées sur 80,
95 %). Ce compte rendu remplace celui de midi et en reprend le résultat. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** Mi-parcours : `origin/main` = `9f030f350`. Clôture : `f46afed2b`. Branche de claim : `verifie-adcg-cloture-1011`.
- **Registre.** PF3 `deploy-ci-gardes`, groupe ADCG, 76 tâches cochées sur 80 constructibles.
- **Échantillons (graine = SHA).** Mi-parcours : les 9 P0 / P1 d'alors + 10 tirées = 19 tâches (ADCG12, 30, 33, 35, 36, 39, 40,
  44, 51, 62, 64, 66, 75, 77, 80, 82, 87, 94, 96). Clôture, les 19 exclues : les 13 prioritaires cochées depuis (ADCG1, 5, 7,
  8, 9, 13, 31, 34, 37, 60, 61, 98, 104) + 11 tirées parmi les 44 autres (ADCG10, 11, 18, 38, 49, 50, 52, 71, 73, 74, 79)
  = 24 tâches. Soit **43 tâches** relues sur 76.
- **Pile locale.** Aucune ; verdicts par lecture des commits et du code sur `origin/main`, par les tests Python purs des
  scripts et les sondes hôte lancés sur l'hôte, et par les enregistrements d'acceptation du 10/11. Aucune lecture de la
  production.

## 1. Vérificateurs (6 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **39** | mi-parcours : ADCG12, 30, 33, 35, 36, 39, 40, 44, 51, 62, 64, 66, 75, 77, 80, 87, 94 ; clôture : ADCG1, 5, 7, 8, 9, 10, 11, 13, 18, 31, 34, 38, 49, 50, 52, 60, 61, 71, 74, 79, 98, 104 |
| partiel | **4** | mi-parcours : ADCG82, ADCG96 (corrigées depuis par ADCG101-102) ; clôture : ADCG37 (procédure écrite avec un nom de service faux), ADCG73 (le test de charge mesure une société vide) |
| non-fait / faux / régression | **0** | — |

Tiennent en particulier, à la clôture : le deploy manuel qui déclenche la même séquence que le deploy automatique (ADCG1) ; le
retour au dernier commit sain quand un deploy échoue après la mise à jour du code — code, images et services (ADCG5) ; la
configuration du serveur web validée avant d'être rechargée, et dans la CI (ADCG8, ADCG9) ; le contrôle de santé qui répond
« indisponible » quand Redis est injoignable (ADCG13) ; l'état de la copie de sauvegarde hors serveur rendu visible — tant que
la destination n'est pas décidée (D-ADCG-1), l'écran affiche « non configurée » et non un état rassurant (ADCG31) ; un simple
comptage qui n'est plus présenté comme une sauvegarde (ADCG34) ; les deux dépendances vulnérables montées à une version
corrigée (ADCG60, ADCG61). Aucun chemin n'a été trouvé qui laisse le serveur sur du code neuf avec des migrations non
appliquées sans retour arrière ni échec au journal, à une réserve près (§4, dernière ligne).

## 2. Tests nommés

Tous présents et comportementaux. Lancés sur l'hôte à la clôture, tous verts : le banc du script de deploy (14 tests), les
tests des gardes et scripts relus (plus de 160 tests `unittest`), deux tests du navigateur sans dépendance. Les tests Django
et ceux du navigateur avec dépendances n'ont pas été rejoués ici : ils ont tourné dans la CI des PR qui les ont portés,
vertes à la fusion. Le test d'ADCG11 joue son cas sur des données en mémoire, pas sur un fichier copié.

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| sondes hôte du deploy, de la santé, du filtre des changements et des dépendances (8) | ADCG1, 5, 7, 8, 10, 13, 60-61, 71 | rejouées sur l'hôte : repro False |
| sondes 012 et 017 du dossier PF3 | ADCG31, ADCG38 | **périmées** (faux modules incomplets depuis les correctifs) ; réalignées dans cette PR : repro False sur `f46afed2b`, repro True sur l'arbre d'avant correctif |
| sondes 013, 014, 015, 018 | ADCG33, 35, 36, 40 | réalignées à mi-parcours (PR #1331) |

Preuves en direct : les enregistrements d'acceptation du 10/11 couvrent les tâches du deploy, de la restauration, de la
pagination des visites et du registre ; ils ont été lus, pas rejoués. ADCG18 (échecs de tâches planifiées au journal des
problèmes) n'est dans aucun enregistrement alors que sa preuve le demandait.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ADCG-VER1-096 | ADCG96 | S3 | (mi-parcours) la procédure de reconstruction du serveur démarrait le deploy automatique avant la restauration | STATIQUE (lecture) | ADCG102 (cochée) |
| C-ADCG-VER1-082 | ADCG82 | S3 | (mi-parcours) la garde jumelle des tests sautés ne voyait pas un saut par exception | STATIQUE (lecture) | ADCG101 (cochée) |
| C-ADCG-VER3-037 | ADCG37 | S3 | la procédure de restauration de la production nomme un service qui n'existe pas (deux commandes échouent telles qu'écrites) et ne dit pas où lancer la vérification finale ; la commande elle-même est juste et a été jouée en direct, mais pas le texte de la procédure | STATIQUE (lecture) | — corrigé dans cette PR (documents sans propriétaire) ; rejeu mot pour mot dû |
| C-ADCG-VER3-073 | ADCG73 | S3 | le test de charge crée son compte dans une société vide et peuple d'autres sociétés : il mesure des listes vides ; aucun lancement depuis le correctif | STATIQUE (lecture) | ADCG105 |
| C-ADCG-VER3-104 | ADCG104 | S3 | le registre ne cherche les tâches d'écart qu'à la date du dernier compte rendu : un groupe dont l'écart ouvert vit dans un bloc plus ancien (calepinage, analyse) ne sera jamais annoncé dû quand sa tâche sera cochée | STATIQUE (lecture, essai du script) | ADCG106 |
| C-ADCG-VER3-005 | ADCG5 | S3 | deux trous du retour arrière, lus dans le script : le serveur web n'est pas rechargé sur la configuration revenue ; si la reconstruction de l'ancien commit échoue, le service est quand même relancé (image neuve, code ancien) | STATIQUE (lecture) | ADCG107 |
| C-ADCG-VER3-001 | ADCG1 | S3 | un deploy « zéro coupure » demandé alors qu'il n'y a rien à déployer laisse son drapeau sur le serveur : il s'appliquera au prochain deploy automatique | STATIQUE (lecture) | ADCG108 |
| C-ADCG-VER3-002 | ADCG2 | S3 (à confirmer) | le code neuf serait visible des processus en marche pendant le build, avant les migrations (déduit à la lecture, non reproduit) | STATIQUE (lecture) | TACHE_109 |

Aucun écart S1-S2 : ni seconde lentille ni critique (METHODE §C.4).

## 5. Optionnel (non déposé)

- ADCG31 : la cause d'un échec de copie est servie mais pas affichée ; une copie réussie ancienne n'a pas d'état « périmée » ;
  l'état « non configurée » n'alimente aucune alerte (visible à l'écran seulement).
- ADCG37 : la restauration ne lit que le stockage local (rien si le serveur est perdu : lié à D-ADCG-1) ; les fichiers
  reviennent dans leur état actuel, pas dans celui du jour de la sauvegarde.
- ADCG61 : la couche de compatibilité ajoutée pour la montée de version remplace des fonctions internes de la bibliothèque,
  fragile à la prochaine montée.
- Mi-parcours : voir le compte rendu de la PR #1331 (sauvegarde des fichiers : copie orpheline après un échec, pas de retour
  à une date donnée ; verdict de rendu ; lead en file de secours).

## 6. Couverture et sortie de cycle

- **Couvert.** 43 tâches sur 76 cochées, dont toutes les prioritaires ; lecture du code et des commits, tests des scripts
  lancés, 10 sondes rejouées sur l'hôte.
- **Non couvert.** Les 33 autres tâches cochées ; aucun rejeu en direct par cette contre-visite ; aucune lecture de la
  production (le serveur exécute-t-il déjà le nouveau script de deploy ?) ; les quatre tâches encore ouvertes du groupe
  (acceptation et décisions D-ADCG-1 à D-ADCG-3).
- **Statut.** Clôture sans écart S1-S2 ⇒ ADCG passe « vérifié » pour sa part construite ; restent les tâches d'écart S3.

## 7. Coût

- Mi-parcours : 3 vérificateurs + 1 rédacteur ≈ 0,8 M de jetons. Clôture : 3 vérificateurs + 1 rédacteur (opus, effort
  élevé) ≈ 1 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ADCG | pct: 95 | ecarts_s1_s2: 0 -->
