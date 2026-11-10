# Vérifie ASOC — contre-visite de clôture du parcours PF2 « socle », 10/11/2026

Commande `loop audit` (10/11). L'audit de parcours PF2 (08/11, PR #1304) avait déposé ASOC1-104. Deux contre-visites le même
jour : mi-parcours le matin (31/36 cochées, PR #1312), puis clôture après la fusion de la PR #1314 (35/35 tâches constructibles
cochées). Ce compte rendu remplace celui du matin et en reprend le résultat. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** Mi-parcours : `origin/main` = `3a9182b4e`. Clôture : `edc0d8ff3`. Branche de claim : `verifie-asoc-cloture-1011`.
- **Registre.** PF2 `socle`, groupe ASOC, 35 tâches cochées sur 35 constructibles ; les autres attendent une décision.
- **Échantillons (graine = SHA).** Aucune tâche P0 / P1 / S1 n'est cochée. Mi-parcours : ASOC4, 7, 31, 70, 72, 83, 85, 87. Clôture,
  tirée parmi les 27 autres : ASOC5, 8, 20, 27, 32, 80, 82, 86. Soit **16 tâches** relues sur 35.
- **Pile locale.** Aucune sonde rejouée ; verdicts par lecture des commits, du code sur `origin/main` et des tests nommés.

## 1. Vérificateurs (2 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **13** | ASOC4, 5, 8, 20, 27, 31, 32, 70, 72, 82, 83, 85, 87 |
| partiel | **3** | ASOC7 (test par lecture du source), ASOC80 (jumeau du calcul de pause), ASOC86 (relance périmée gardée) |
| non-fait / faux / régression | **0** | — |

## 2. Tests nommés

Tous présents ; treize sont comportementaux. ASOC7 vérifie la présence d'un filtre par lecture de l'arbre syntaxique. Le test
d'ASOC86 supprime toutes les relances avant de restaurer le lead : il ne joue jamais le cas décrit par sa propre tâche. Le test
d'ASOC20 vit sous une autre classe que celle annoncée (dit dans le commit). Aucun test rejoué en local (CI d'abord).

## 3. Sondes

Aucune des seize tâches ne s'appuie sur une sonde du dossier PF2 rejouable ici ; rien n'a été rejoué.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ASOC-VER2-080 | ASOC80 | S3 | l'échéance SAV suit le calendrier de la société, mais les jours de pause sont encore comptés sur un calendrier codé en dur : pour une société ouverte le samedi, l'échéance tombe un jour trop tôt | STATIQUE (lecture) | ASOC105 |
| C-ASOC-VER2-086 | ASOC86 | S3 | un lead restauré de la corbeille garde pour seule prochaine étape une relance déjà périmée ; le test contourne ce cas | STATIQUE (lecture) | ASOC106 |
| C-ASOC-VER1-007 | ASOC7 | S4 | le test de non-contagion entre sociétés est une lecture du source, pas un rejeu à deux sociétés | STATIQUE (lecture) | — (cosmétique) |

Aucun écart S1-S2 : ni seconde lentille ni critique (METHODE §C.4).

## 5. Optionnel (non déposé)

- ASOC83 : le sujet du rappel de rendez-vous de la veille reste en français en dur ; un modèle rempli seulement en arabe n'est
  pas servi en arabe.
- ASOC87 : la facture consolidée ne reprend pas l'escompte par défaut.
- ASOC27 : le test du jalon ne vérifie que la cloche, pas l'e-mail du portail.
- ASOC20 : la demande de contrat du portail s'affiche dans la catégorie « général » au lieu de « SAV ».
- ASOC32 : au premier passage après le deploy, un doublon de rappel de calibration est possible par outil.
- ASOC80 : sans jours fériés enregistrés pour la société, le délai SAV ne saute plus aucun férié (non vérifié en prod).
- Acceptation : aucun enregistrement `docs/audits/acceptation/ASOC/` ; les seize tâches sont « API seulement ».

## 6. Couverture et sortie de cycle

- **Couvert.** 16 tâches sur 35 cochées ; lecture du code, des commits et des tests.
- **Non couvert.** Les 19 autres tâches cochées ; les tâches du groupe en attente de décision (dont celle du constat grave de
  l'audit : l'échéancier d'un devis envoyé lu en direct) ne sont pas construites ; aucune sonde ; aucun rejeu navigateur.
- **Statut.** Clôture sans écart S1-S2 ⇒ ASOC passe « vérifié » pour sa part construite ; restent les deux tâches d'écart.

## 7. Coût

- 2 vérificateurs + 1 rédacteur (opus, effort élevé) ≈ 0,55 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ASOC | pct: 100 | ecarts_s1_s2: 0 -->
