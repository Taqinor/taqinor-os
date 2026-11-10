# Vérifie APFS — contre-visite de clôture du parcours PF1 « sécurité / multi-société », 10/11/2026

Commande `loop audit` (10/11). L'audit de parcours PF1 (08/11, PR #1302) avait déposé APFS1-117. Deux contre-visites le même
jour : mi-parcours le matin (20 cochées, PR #1313, qui a déposé APFS118-119), puis clôture après la fusion des PR #1314 et #1316
(23/23 tâches constructibles cochées). Ce compte rendu remplace celui du matin et en reprend le résultat. Rien n'a été construit
ni déployé.

## 0. Préconditions

- **SHA.** Mi-parcours : `origin/main` = `3a9182b4e`. Clôture : `9f030f350`. Branche de claim : `verifie-apfs-cloture-1011`.
- **Registre.** PF1 `securite-multi-societe`, groupe APFS, 23 tâches cochées sur 23 constructibles ; les autres attendent une
  décision.
- **Échantillons (graine = SHA).** Mi-parcours : les 2 P0 (APFS100, APFS101) + APFS28, 43, 46, 60, 62, 64. Clôture, tirée parmi
  les 15 autres (aucune P0 / P1 / S1 restante) : APFS22, 41, 63, 65, 104, 114, 118, 119. Soit **16 tâches** relues sur 23.
- **Pile locale.** Aucune ; verdicts par lecture des commits et du code sur `origin/main`, par les gardes et leurs tests
  Python purs lancés sur l'hôte, et par des essais en mémoire (rien écrit au dépôt).

## 1. Vérificateurs (2 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **14** | APFS22, 28, 41, 43, 46, 60, 62, 65, 100, 101, 104, 114, 118, 119 |
| partiel | **2** | APFS64 (mi-parcours : garde d'isolement, corrigée depuis par APFS118-119), APFS63 (la garde des balayages planifiés ne voit pas tous les modèles) |
| non-fait / faux / régression | **0** | — |

Aucune fuite entre sociétés ni droit accordé trop largement n'a été trouvé. Tiennent en particulier, à la clôture : le rendu
d'un gabarit refusé à un rôle sans droit sur le module de la fiche, coordonnées du client masquées sans le droit de les voir
(APFS22) ; le plan de quotas d'API réservé au palier administrateur (APFS41) ; le superutilisateur rattaché à une société borné
à celle-ci dans les droits de la GED (APFS114) ; les trois balayages planifiés des rapports bornés aux sociétés actives
(APFS63, pour le code) ; la garde d'isolement qui lit maintenant les 278 vues fonction du dépôt, aucune oubliée (APFS118).

## 2. Tests nommés

Tous présents et comportementaux. Lancés sur l'hôte, tous verts : la garde d'isolement et ses 19 tests, la garde des balayages
planifiés et ses tests, la garde des références entre sociétés et ses 30 tests. Deux mutants joués en mémoire font bien échouer
les tests d'APFS118 et d'APFS119. Les tests Django (APFS22, 41, 63, 104, 114) n'ont pas été rejoués ici (CI des PR #1314 et
#1316, vertes à la fusion). Tests faibles : APFS63 ne teste que l'un des trois balayages ; dans APFS22, l'assertion sur le
ticket ne prouve rien (la fiche visée n'existe sans doute pas) ; APFS43 (mi-parcours) teste la permission sur une vue factice.

## 3. Sondes (dossier PF1)

Les sondes des tâches relues demandent Django : lues, aucune rejouée. Les tâches APFS100, APFS60 et APFS62 annonçaient une sonde
rejouée comme preuve : elle ne l'a pas été.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-APFS-VER1-064 | APFS64 | S3 | (mi-parcours) la garde d'isolement n'ouvrait que les fichiers nommés « vues » et acceptait tout mot « company » | STATIQUE (lecture) | APFS118, APFS119 (cochées, relues ok) |
| C-APFS-VER2-063 | APFS63 | S3 | la garde des balayages planifiés ne reconnaît que les modèles qui déclarent eux-mêmes leur société : un modèle qui l'hérite (cas des abonnements de rapports) lui échappe ; rejouée sur le code d'avant correctif, elle ne signale pas ce balayage ; deux des trois balayages n'ont pas de test « société suspendue » | STATIQUE (lecture) | APFS120 (garde), APFS122 (tests) |
| C-APFS-VER2-064 | APFS118, APFS119 | S3 | le critère de la garde d'isolement n'est fermé qu'à moitié : un appel dont le NOM contient « company » vaut encore filtre, quoi qu'il fasse ; des vues ne passent la garde que par ce nom (relues bornées autrement : aucune fuite) | STATIQUE (lecture) | APFS121 |

Aucun écart S1-S2 : ni seconde lentille ni critique (METHODE §C.4).

## 5. Optionnel (non déposé)

- APFS118 : les vues classes rangées hors des fichiers « vues » ne sont pas contrôlées (21 trouvées, relues bornées) ; la vue
  des utilisateurs, bien bornée, est gelée en dette : le retrait de sa borne passerait inaperçu.
- APFS119 : un filtre « société non vide » suffit à la garde, de même qu'un filtre société posé sur une autre requête que la
  lecture (cas hypothétiques).
- APFS22 : l'adresse du site d'un chantier n'est pas masquée sans le droit de voir les coordonnées (hors du texte).
- APFS114 : un calcul de justification de la GED garde l'ancien prédicat superutilisateur ; cas inatteignable aujourd'hui.
- Mi-parcours : APFS43 (l'inventaire des gardes ignore une vue dont la permission dépend de la méthode HTTP), APFS46 (le
  service d'actions de l'assistant décide encore sur le rôle du jeton ; Django reste la vraie porte), APFS62 (correctif lu,
  sans test de comportement).
- Acceptation : rejouée en direct par une autre session le même jour (PR #1330, non relue ici).

## 6. Couverture et sortie de cycle

- **Couvert.** 16 tâches sur 23 cochées ; lecture du code, des commits et des tests ; gardes et mutants joués sur l'hôte.
- **Non couvert.** Les 7 autres tâches cochées ; aucune sonde rejouée ; aucun rejeu à deux comptes en direct ; les tâches du
  groupe en attente de décision ne sont pas construites. Les balayages planifiés (9, comptage du rédacteur) et les vues (6)
  que les deux gardes corrigées révéleront n'ont pas été relus un à un : « aucune fuite prouvée », pas « aucune fuite ».
- **Statut.** Clôture sans écart S1-S2 ⇒ APFS passe « vérifié » pour sa part construite ; restent les tâches d'écart ouvertes.

## 7. Coût

- 2 vérificateurs + 2 rédacteurs (opus, effort élevé) ≈ 1 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: APFS | pct: 100 | ecarts_s1_s2: 0 -->
