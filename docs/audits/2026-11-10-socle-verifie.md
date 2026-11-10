# Vérifie ASOC — contre-visite de mi-parcours du parcours PF2 « socle », 10/11/2026

Commande `loop audit` (10/11). L'audit de parcours PF2 (08/11, PR #1304) avait déposé ASOC1-104 ; 31 tâches constructibles sur 36
sont cochées (86 %) depuis la fusion de la PR #1308 : la contre-visite de mi-parcours est due. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `3a9182b4e` (relectures). Branche de claim : `verifie-asoc-1011`.
- **Registre.** PF2 `socle`, groupe ASOC, 31 tâches cochées sur 36 constructibles (les autres sont en attente ou bloquées).
- **Échantillon (graine = SHA `3a9182b4e`).** Aucune tâche P0 / P1 / S1 cochée ; 8 tirées (minimum de la méthode) : ASOC4, 7, 31,
  70, 72, 83, 85, 87.
- **Pile locale.** Checkout principal en retard de plus de 6 000 commits : aucune sonde rejouée ; verdicts par lecture des
  commits, du code sur `origin/main` et des tests nommés.

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **7** | ASOC4, 31, 70, 72, 83, 85, 87 |
| partiel | **1** | ASOC7 (code conforme aux trois emplacements ; le test nommé lit le source au lieu de rejouer le Then) |
| non-fait / faux / régression | **0** | — |

## 2. Tests nommés

Sept tests sur huit sont comportementaux (état relu en base, message réellement envoyé, réponse). Celui d'ASOC7 vérifie par
lecture de l'arbre syntaxique qu'un filtre société est présent : une valeur fausse passerait. Le module désigné par la tâche est
un test sans base de données : le défaut vient du texte de la tâche autant que de sa construction. Aucun test rejoué (CI d'abord).

## 3. Sondes

Aucune des huit tâches ne s'appuie sur une sonde du dossier PF2 rejouable ici ; rien n'a été rejoué.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ASOC-VER1-007 | ASOC7 | S4 | le test de non-contagion entre sociétés est une lecture du source, pas un rejeu à deux sociétés | STATIQUE (lecture) | — (cosmétique : à durcir à la contre-visite de clôture si le test n'a pas changé) |

Aucun écart S1-S2 ni S3 : aucune tâche déposée, ni seconde lentille ni critique.

## 5. Optionnel (non déposé)

- ASOC83 : le sujet du rappel de rendez-vous de la veille reste en français en dur ; une société qui ne remplit que le sujet
  arabe d'un modèle n'obtient pas son arabe (le choix « personnalisé » se lit sur le champ français).
- ASOC87 : la facture consolidée ne reprend pas l'escompte par défaut (hors du Then).
- ASOC70 : le réglage de parrainage éteint par défaut arrête le parrainage automatique tant que personne ne l'allume (annoncé).
- ASOC72 : budget « lignes nettes » dépassé (dit dans le commit).
- Acceptation : aucun enregistrement `docs/audits/acceptation/ASOC/` ; les huit tâches sont « API seulement ».

## 6. Couverture et suite

- **Couvert.** 8 tâches sur 31 cochées ; lecture du code, des commits et des tests.
- **Non couvert.** Les 23 autres tâches cochées ; aucune sonde ; aucun rejeu navigateur ; aucune tâche P0 / S1 du groupe n'est
  encore cochée (elles restent à construire ou en attente de décision).
- **Statut.** Mi-parcours sans écart S1-S3 ; la contre-visite de clôture sera due à 95 %.

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,25 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ASOC | pct: 86 | ecarts_s1_s2: 0 -->
