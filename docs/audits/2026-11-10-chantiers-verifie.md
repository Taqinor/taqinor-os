# Vérifie ACHT — contre-visite des correctifs de l'unité J2 « chantiers », 10/11/2026

Commande `loop audit` (10/11). La contre-visite du 04/11 (`docs/audits/2026-11-04-chantiers-verifie.md`) avait trouvé 2 écarts
S2 ; les 8 tâches d'écart ACHT130-137 ont été construites et cochées depuis, sans jamais être relues. Contre-visite lancée à la
main (le script de registre ne la redemande pas). Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `c1a99568a`. Branche de claim : `verifie-correctifs-lot1-1011`.
- **Registre.** J2 `chantiers`, groupe ACHT, 122 tâches cochées sur 122.
- **Échantillon.** Les 8 tâches d'écart du 04/11, toutes cochées : ACHT130 à ACHT137.
- **Pile locale.** Aucune ; verdicts par lecture des commits, du code sur `origin/main` et des tests nommés ; un test du
  navigateur hors ligne lancé sur l'hôte (5 réussis).

## 1. Vérificateur (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **8** | ACHT130, 131, 132, 133, 134, 135, 136, 137 |
| partiel / non-fait / faux / régression | **0** | — |

Les deux écarts S2 du 04/11 sont fermés : une heure saisie hors ligne invraisemblable est ramenée à l'heure de synchronisation
et une durée négative devient « inconnue » — plus de milliers d'heures de main-d'œuvre sur une facture (ACHT130, ACHT131) ; la
replanification depuis l'agenda d'un chantier ou d'une intervention hors de sa portée répond « introuvable » sans rien écrire
(ACHT137).

## 2. Tests nommés

Tous présents et comportementaux (API de synchronisation, dates relues, journal relu). Pour ACHT137, le test accepte deux codes
de refus pour le rôle commercial là où la tâche en nomme un ; les dates relues inchangées interdisent de toute façon un succès.

## 3. Sondes

Les sept sondes de la contre-visite du 04/11 demandent Django : lues, non rejouées. Aucune trace d'un rejeu après correctif
n'existe pour six tâches qui l'annonçaient comme preuve (ACHT130, 131, 133, 134, 136, 137) : seuls leurs tests les prouvent.
ACHT132 et ACHT135 ont un rejeu en direct consigné (`docs/audits/acceptation/ACHT/`).

## 4. Écarts retenus

Aucun.

## 5. Optionnel (non déposé)

- ACHT130 : la fenêtre de sept jours laisse jusqu'à 168 heures de main-d'œuvre sur une facture brouillon (choix écrit dans la
  tâche) ; le rejeu d'une même saisie n'a pas de test propre.
- ACHT132 : une saisie fusionnée après un premier envoi expiré sortira en conflit (visible, rejouable, sans perte).
- ACHT136, ACHT137 : les activités de l'agenda ne sont bornées par la portée ni en lecture ni en écriture (hors tâche).

## 6. Couverture et sortie de cycle

- **Couvert.** Les 8 tâches d'écart ; lecture du code, des commits et des tests.
- **Non couvert.** Les 114 autres tâches cochées (échantillonnées par les contre-visites précédentes) ; aucune sonde rejouée ;
  l'effet à l'écran n'a été vu que pour ACHT132 et ACHT135.
- **Statut.** 0 écart S1-S2 ⇒ ACHT passe « vérifié ».

## 7. Coût

- 1 vérificateur (opus, effort élevé) ≈ 0,2 M de jetons ; aucun appel Fable.

<!-- verifie | groupe: ACHT | pct: 100 | ecarts_s1_s2: 0 -->
