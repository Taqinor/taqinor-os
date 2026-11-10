# Vérifie APRF — contre-visite des correctifs de l'unité X6 « performance », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 04/11 (`docs/audits/2026-11-04-performance-verifie.md`) avait trouvé
1 écart S2 ; les 3 tâches d'écart APRF43-45 ont été construites et cochées depuis, sans jamais être relues. Contre-visite des
correctifs (METHODE §C.4 point 6). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot3-1011`.
- **Registre.** X6 `performance`, groupe APRF, 41 tâches cochées sur 41.
- **Échantillon.** Les 3 tâches d'écart du 04/11, cochées : APRF43, APRF44, APRF45 (acceptation).
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main`, des tests nommés et de
  l'enregistrement d'acceptation du 04/11 ; trois gardes du dépôt lancées sur l'hôte (vertes).

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **3** | APRF43, 44, 45 |
| partiel / non-fait / faux / régression | **0** | — |

L'écart S2 du 04/11 est fermé : l'export asynchrone des mouvements de stock est de nouveau téléchargeable — le lien de la
notification est servi par l'ERP, borné à la société de l'utilisateur, valable 24 heures, et le fichier est le même que celui
de l'export immédiat (APRF43). Les comptes de clients (portefeuille, comptes dormants) comptent maintenant la version signée
en vigueur d'un devis révisé, sans double comptage (APRF44). Résultats identiques vérifiés : aucun correctif de performance
ne change un total ni n'ouvre une autre société.

## 2. Tests nommés

Présents et comportementaux, jamais retouchés ; verts dans la CI de la PR qui les a portés. La spec d'acceptation rejoue le
geste réel (export, notification, clic, téléchargement, refus sous une autre société).

## 3. Sondes

La sonde de l'écart S2 demande Django : lue, non rejouée. L'enregistrement d'acceptation du 04/11
(`docs/audits/acceptation/APRF/`) couvre les trois tâches — mais il a été joué AVANT un resserrement ultérieur du droit de
téléchargement : le téléchargement sous la garde actuelle n'a pas été rejoué en direct.

## 4. Écarts retenus

Aucun.

## 5. Optionnel (non déposé)

- Dans la spec d'acceptation, le contrôle de la durée de 24 heures lit un champ mal nommé et n'est donc jamais joué (la durée
  reste couverte par le test unitaire).
- Jumeau encore ouvert, hors de la tâche : l'API publique sert toujours des adresses de stockage signées pour ses résultats.
- Le calcul des devis signés en vigueur charge toutes les révisions acceptées de la société à chaque appel.
- Toujours ouverts depuis le 04/11, hors tâches d'écart : un budget de requêtes en attente de décision et trois tâches en
  dette d'acceptation.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 3 tâches d'écart ; lecture du code, des commits, des tests et de l'enregistrement d'acceptation.
- **Non couvert.** Les 38 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; aucune sonde ni test
  rejoué ; le téléchargement depuis la cloche sous la garde actuelle.
- **Statut.** 0 écart S1-S2 ⇒ APRF passe « vérifié ».

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: APRF | pct: 100 | ecarts_s1_s2: 0 -->
