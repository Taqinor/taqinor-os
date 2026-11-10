# Vérifie AARG — contre-visite des correctifs du parcours PA4 « argent », 10/11/2026

Commande `loop audit` (10/11). La contre-visite de clôture du 05/11 (`docs/audits/2026-11-05-argent-verifie.md`) avait trouvé
5 écarts S1-S2 ; les 13 tâches d'écart AARG59-71 ont été construites et cochées depuis, sans jamais être relues. Le groupe compte
70 tâches cochées sur 71 (AARG50, l'acceptation, reste ouverte). Le script de registre ne redemande pas de contre-visite après
une première clôture : celle-ci est lancée à la main, pour le groupe qui touche l'argent. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `8703fdfde`. Branche de claim : `verifie-aarg-1011`.
- **Registre.** PA4 `argent`, groupe AARG, 71 tâches, 70 `[x]`.
- **Échantillon (graine = SHA `8703fdfde`).** Les 13 tâches d'écart cochées + 6 tâches d'origine tirées = **19 tâches**, 2 lots.
- **Pile locale.** Checkout principal en retard de plus de 6 000 commits : aucune sonde rejouée ; verdicts par lecture des
  commits, du code sur `origin/main` et des tests nommés. Les vues de facturation ont été déplacées le 08/11 (déplacement pur) :
  le code a été lu à son nouvel emplacement, `apps/facturation/views/`.

## 1. Vérificateurs (2 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **17** | AARG2, 5, 7, 9, 40, 51, 59, 60, 61, 62, 63, 64, 67, 68, 69, 70, 71 |
| partiel | **2** | AARG65, AARG66 (même cause : deux écrans d'analyse oubliés) |
| non-fait / faux / régression | **0** | — |

Les cinq écarts S1-S2 du 05/11 sont fermés : annulation d'un avoir qui rend le trop-perçu (AARG59), restauration d'une facture
bornée au prix convenu (AARG63), effets d'une annulation rejoués à la restauration, retenue comprise (AARG64), relance qui ne se
consigne pas quand l'envoi échoue (AARG69), bon de commande refusé sur une version de devis remplacée (AARG68).

## 2. Tests nommés

Tous présents et comportementaux (montant ou statut relu en base, réponse HTTP). Aucun test affaibli : deux tests existants ont
été réalignés sur le comportement voulu (trop-perçu rendu, 502 quand l'envoi échoue). Tests faibles sans effet sur le verdict :
AARG7 (le rôle autorisé n'est testé que par « pas 403 »), AARG70 (assertion de liste qui passe aussi si la facture est absente),
AARG64 (la variante « transférer » rend bien 409 mais n'a pas de test). Aucun test rejoué en local (CI d'abord).

## 3. Sondes (dossier PA4 et sondes de la contre-visite du 05/11, lues, non rejouées)

| Sonde | Tâche | Verdict |
|---|---|---|
| sonde 002 du dossier PA4 ; sondes 001, 002, 010, 020 de la contre-visite du 05/11 | AARG2, 64, 63, 69, 68 | lecture : passeraient à repro False |
| sondes 003 et 011 de la contre-visite du 05/11 | AARG66, AARG65 | lecture : repro False (toutes les routes répondent 403 au rôle sans droit) |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AARG-VER6-065 | AARG65, AARG66 | S3 | deux écrans d'analyse (balance âgée, du devis à l'encaissement) restent offerts par le menu à des rôles qui reçoivent désormais 403 ; l'écran affiche « serveur indisponible » ; aucune donnée exposée | STATIQUE (lecture) | AARG72 |

Aucun écart S1-S2 : ni seconde lentille ni critique (METHODE §C.4).

## 5. Optionnel (non déposé)

- AARG63 : la restauration est bornée au prix convenu, pas à la tranche — un acompte annulé puis ré-émis, puis l'avoir annulé,
  donne deux acomptes pour une seule tranche tant que la somme reste sous le prix. Question de règle, non sondée.
- AARG7 : la directive « garder en avance » d'une annulation n'exige pas le droit d'encaisser (le Then ne visait que rembourser
  et transférer).
- AARG70 : l'échéance dérivée suit le délai ACTUEL du client, pas celui de l'émission ; une note de débit sur une facture sans
  échéance court à 30 jours par défaut.
- AARG71 : une restauration vers une version de devis remplacée garde le message d'émission.
- Annulation d'un avoir non relue sous verrou : deux requêtes simultanées pourraient l'annuler deux fois (antérieur au groupe).
- Couverture d'acceptation : AARG5, 7, 9, 40 et 51 se disent « rejouées par AARG50 », dont l'enregistrement ne les liste pas ;
  AARG59-62, 65, 66, 67 et 70 n'ont aucun enregistrement (déclarées « API seulement »).

## 6. Couverture et sortie de cycle

- **Couvert.** 19 tâches sur 70 cochées, dont les 13 tâches d'écart ; lecture du code, des commits et des tests.
- **Non couvert.** Les 51 autres tâches cochées (dont 32 relues le 05/11) ; aucune sonde rejouée ; aucun rejeu navigateur.
- **Statut.** 0 écart S1-S2 ⇒ AARG passe « vérifié » ; il reste AARG50 (acceptation) et AARG72 à cocher.

## 7. Coût

- 2 vérificateurs + 1 rédacteur (opus, effort élevé) ≈ 0,7 M de jetons ; aucun appel Fable (aucun S1).

<!-- verifie | groupe: AARG | pct: 98 | ecarts_s1_s2: 0 -->
