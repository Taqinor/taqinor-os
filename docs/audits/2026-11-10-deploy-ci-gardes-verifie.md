# Vérifie ADCG — contre-visite de mi-parcours du parcours PF3 « deploy / CI / gardes », 10/11/2026

Commande `loop audit` (10/11). L'audit de parcours PF3 (10/11, PR #1310) avait déposé ADCG1-100 ; 48 tâches constructibles sur
52 sont cochées (92 %) depuis la fusion des PR #1314 et #1316 : la contre-visite de mi-parcours est due. Rien n'a été construit
ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `9f030f350`. Branche de claim : `verifie-adcg-1011`.
- **Registre.** PF3 `deploy-ci-gardes`, groupe ADCG, 48 tâches cochées sur 52 constructibles.
- **Échantillon (graine = SHA `9f030f350`).** Les 9 tâches P0 / P1 cochées (ADCG12, 30, 33, 36, 51, 62, 64, 94, 96) + 10 tirées
  parmi les 39 autres (ADCG35, 39, 40, 44, 66, 75, 77, 80, 82, 87) = **19 tâches**, 3 lots.
- **Pile locale.** Aucune ; verdicts par lecture des commits et du code sur `origin/main`, par les tests Python purs des scripts
  (lancés sur l'hôte) et par les sondes hôte. Aucune lecture de la production.

## 1. Vérificateurs (3 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **17** | ADCG12, 30, 33, 35, 36, 39, 40, 44, 51, 62, 64, 66, 75, 77, 80, 87, 94 |
| partiel | **2** | ADCG82 (garde jumelle laissée telle quelle), ADCG96 (ordre de la procédure de reconstruction) |
| non-fait / faux / régression | **0** | — |

Tient en particulier la tâche grave du groupe, relue deux fois (ADCG30) : chaque sauvegarde planifiée copie maintenant les
fichiers métier des deux espaces de stockage, ne supprime jamais une copie, finit en échec en nommant l'espace fautif, et la
restauration sait les recopier. Tiennent aussi : la purge d'une société refusée sans sauvegarde restaurable prise après sa
fermeture (ADCG33), l'alerte quand aucun exercice de restauration n'a jamais réussi (ADCG36), les deux gardes de dépendances
réellement bloquantes (ADCG62), l'échec du deploy automatique consigné dans le journal des problèmes (ADCG12).

## 2. Tests nommés

Tous présents et comportementaux. Lancés sur l'hôte, tous verts : les tests des scripts des lots « CI » et « gardes » (près de
180 tests `unittest`, dont les 107 du module de fuzz) et un test du script de deploy. Les tests Django (ADCG30, 33, 35, 36, 39,
40, 44, 94) et le test du site public (ADCG51) n'ont pas été rejoués ici : ils ont tourné dans la CI des PR #1314 et #1316,
vertes à la fusion — les journaux des lots de tests n'ont pas été relus un à un. Le test d'ADCG82 s'arrête à la fonction de
détection, sans jouer la garde de bout en bout.

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| sondes des constats de dépendances et de fuzz | ADCG62, ADCG64 | rejouées sur l'hôte : repro False |
| sondes 013, 014, 015, 018 du dossier PF3 | ADCG33, 35, 36, 40 | **périmées** : elles plantaient sur `origin/main` (faux modules incomplets depuis les correctifs) ; réalignées dans cette PR, rejouées : repro False sur `9f030f350`, repro True sur l'arbre d'avant correctif (`dc496b27b`) |
| sonde du deploy en échec | ADCG12 | lue, non rejouée |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ADCG-VER1-096 | ADCG96 | S3 | la procédure « Reconstruire le serveur » démarre le deploy automatique à l'étape 4, avant le démarrage manuel de la pile et avant la restauration des données : un deploy complet partirait sur une base vide, en même temps que le démarrage manuel | STATIQUE (lecture) | ADCG102 |
| C-ADCG-VER1-082 | ADCG82 | S3 | la garde jumelle des tests sautés sans raison valable ne voit toujours pas un test sauté par `raise SkipTest` ; la tâche demandait de la traiter ; aucun faux vert aujourd'hui (2 sites, aux raisons valides) | STATIQUE (lecture) | ADCG101 |

Aucun écart S1-S2 : ni seconde lentille ni critique (METHODE §C.4).

## 5. Optionnel (non déposé)

- ADCG30 : si la copie des fichiers échoue, la sauvegarde de base déjà envoyée reste orpheline (jamais purgée) ; un fichier
  modifié écrase sa copie (pas de retour à une date donnée) ; un fichier effacé à la demande d'un client reste dans la copie ;
  l'échec de la copie distante des fichiers n'apparaît pas dans le message du run. La copie reste sur le même disque tant que
  la décision D-ADCG-1 (copie hors serveur) est ouverte.
- ADCG12 : les sorties d'erreur d'avant le deploy (récupération du code en échec) ne sont pas consignées.
- ADCG35 : une limite de temps atteinte pendant le nettoyage final, après un exercice réussi, laisserait le run « en cours ».
- ADCG44 : toute erreur de valeur du constructeur devient un verdict critique, même une vraie panne ; un verdict ouvert sur un
  devis archivé ensuite n'est jamais résolu.
- ADCG51 : un lead d'abord refusé pour indisponibilité puis refusé pour identifiants garde son expiration de 7 jours ; un refus
  durable serait signalé indéfiniment toutes les 30 minutes.
- ADCG94 : la mesure suppose que le dossier de l'application repose sur le disque des données (non lu en production).
- ADCG77 : le message d'échec cite une option qui n'existe pas dans ce script.

## 6. Couverture et suite

- **Couvert.** 19 tâches sur 48 cochées, dont les 9 prioritaires ; lecture du code et des commits, tests des scripts lancés,
  6 sondes rejouées.
- **Non couvert.** Les 29 autres tâches cochées ; aucun rejeu en direct (aucune sauvegarde réelle, aucun deploy en échec
  réel, aucune lecture de la production : le serveur exécute-t-il déjà le nouveau script de deploy ?) ; l'acceptation ADCG100
  reste ouverte ; l'étape qui commente l'issue de fuzz (ADCG64) n'a aucun test.
- **Statut.** Mi-parcours sans écart S1-S2 ; la contre-visite de clôture sera due à 95 %.

## 7. Coût

- 3 vérificateurs + 1 rédacteur (opus, effort élevé) ≈ 0,8 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ADCG | pct: 92 | ecarts_s1_s2: 0 -->
