# Vérifie ALEC — contre-visite par anticipation du parcours PF6 « lecture des données sensibles », 13/11/2026

Commande `vérifie ALEC` (13/11), lancée par ANTICIPATION à la demande du fondateur. L'audit de parcours PF6 (11/11) avait
déposé les tâches ALEC ; leur code a été livré par la vague 12 du 11/11, mais 25 d'entre elles restent en attente de leur
preuve en direct et ne sont donc pas cochées. Première contre-visite du groupe. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `d64fa1e4e4`. Branche de travail : `acceptation-runner-1311`.
- **Registre.** PF6 `lecture-sensible`, groupe ALEC : 7 tâches cochées sur 15 constructibles (46 %), sous le seuil de
  mi-parcours. Les 25 tâches « code livré, preuve en direct due » ne comptent pas encore comme cochées sur `main`. Sur la
  branche de travail (pas encore sur `main`), deux enregistrements d'acceptation PASS du 13/11 couvrent ces 25 tâches et
  23 y sont cochées ; ALEC16 et ALEC18 y restent non cochées.
- **Échantillon.** Sur demande du fondateur, les **25 tâches livrées** sont toutes relues, pas un tirage : ALEC1, 2, 3, 4,
  7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20, 21, 25, 26, 27, 36, 37, 38, 39.
- **Méthode.** Lecture des commits, du code sur `origin/main` et des tests nommés, avec un mutant raisonné par tâche ; les
  codes de chaque rôle livré sont lus dans le registre des rôles exécuté hors Django. Deux sondes hôte nouvelles, jouées.
  Aucune pile, aucun test Django lancé, aucune production consultée.

## 1. Vérificateurs (1 lot, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **22** | ALEC1, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13, 14, 15, 19, 20, 21, 26, 27, 36, 37, 38, 39 |
| partiel | **3** | ALEC16 (S2), ALEC18 (S2), ALEC25 (S3, test seulement) |
| non-fait / faux / régression / déjà-présent | **0** | — |

## 2. Tests nommés

Les vingt-cinq tests nommés existent et sont comportementaux : vrais appels HTTP ou vraie garde, rôles pris dans le
registre livré (codes réels de Commercial, Technicien, Directeur, Admin Ventes…), état relu en base quand la tâche écrit.
Parmi les correctifs de CI relus, un seul touche un test ALEC (ALEC37) et il réaligne sans affaiblir. Exception : le test d'ALEC25 crée un rôle nommé « Commercial » avec les codes du Responsable et la portée
d'équipe, au lieu du Commercial livré (portée « soi ») ; le mutant « retirer la portée » reste tué, d'où S3.

## 3. Sondes et preuve en direct

- **ALEC16 — sonde nouvelle 101, reproduit (`repro: true`).** Elle exécute le vrai corps de la garde module et portée de
  l'assistant SQL (parseur bouchonné, sqlglot absent de l'hôte) avec les codes réels du Commercial livré (portée « soi ») :
  la lecture des lignes de factures, des lignes de devis, des équipements et des contrats de maintenance PASSE ; la lecture
  des interventions est refusée faute de droit du module ; le témoin (factures) est refusé « portée restreinte ». Les
  lignes ne sont bornées qu'à la société de leur document parent ; leurs colonnes ne sont pas dans la garde des prix.
- **ALEC18 — sonde nouvelle 102, reproduit (`repro: true`).** Elle exécute les vraies règles d'accès des demandes de
  signature et de leurs destinataires, avec les vraies classes de permission et les codes réels : le Commercial terrain
  (aucun droit GED) franchit la lecture des demandes, du PDF signé et des destinataires, alors que la vue des documents
  corrigée par ALEC18 le refuse (témoin). L'Admin RH (droit GED, sans le droit aux coordonnées des clients) passe aussi.
  Les deux sérialiseurs servent e-mail, téléphone, adresse IP et navigateur des signataires sans consulter ce droit.
- **Sondes du dossier PF6 rejouées telles quelles.** La sonde 014 (assistant SQL) et la sonde 021 (lignes de factures) ne
  reproduisent plus : leurs tables d'origine sont corrigées ; la sonde 014 ne testait pas les tables jumelles. La sonde 003
  affiche encore « reproduit » : faux positif, son bouchon de condition ignore la négation (lecture du vérificateur). Les
  sondes 004, 024 et 025 reproduisent : elles couvrent des tâches encore suspendues à une décision, hors de cette relecture.
  Les sondes 001, 002, 007, 008, 010, 012, 016, 017 et 020 plantent à l'extraction depuis les correctifs ; les sondes
  005, 006, 009, 011, 013, 018, 019, 022 et 023 ne reproduisent plus.
- **Preuve en direct.** Pas rejouée ici. Les deux enregistrements PASS de la branche de travail rejouent le « fini quand »
  d'ALEC16 (devis) et d'ALEC18 (documents) : ils ne touchent ni les lignes de factures ni les demandes de signature, et ne
  contredisent donc pas les deux écarts ci-dessous.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ALEC-VER1-101 | ALEC16 | S2 | la liste des tables bornées au propriétaire de l'assistant SQL oublie les lignes de devis et de factures, les interventions, les équipements et les contrats de maintenance : un Commercial à portée « soi » lit les lignes de factures de toute la société | `docs/audits/sondes/ALEC/C-ALEC-VER1-101.py` | ALEC41 |
| C-ALEC-VER1-102 | ALEC18 | S2 | les deux vues des demandes de signature sont restées ouvertes à tout compte interne : un Commercial terrain sans droit GED, ou un Admin RH sans droit aux coordonnées, lit e-mail, téléphone et adresse IP des signataires | `docs/audits/sondes/ALEC/C-ALEC-VER1-102.py` | ALEC42, ALEC43 |
| C-ALEC-VER1-103 | ALEC25 | S3 | le test prouve la portée avec un rôle fabriqué (codes du Responsable, portée d'équipe), pas avec le Commercial livré | STATIQUE (lecture du test) | ALEC44 |

ALEC18 donne deux tâches parce que ce sont deux comportements : le refus du module (ALEC42) et le masque des coordonnées
pour un rôle qui garde le droit GED (ALEC43).

## 5. Optionnel (non déposé)

- L'aperçu public d'une demande à destinataires reste servi par son jeton global, sans le code à usage unique exigé sur la
  voie destinataire ; depuis ALEC1 ce jeton n'est plus servi à personne : exploitation non prouvée.
- ALEC14 : la règle couvre le coût d'un ticket et d'un mouvement de stock, mais le test ne joue que la marge du devis.
- ALEC15 : la transmission du droit aux coordonnées depuis le contexte d'action n'est pas couverte par un test.
- ALEC39 : le test vérifie la portée sur un lead sans visite validée, ce qui suffit à la portée.
- Autres lectures GED encore ouvertes à tout interne (liens, partages, approbations, annotations, validations OCR) :
  métadonnées de documents, gravité moindre, non sondées ici.
- Rafraîchir les sondes du dossier PF6 qui plantent ou donnent un faux positif.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 25 tâches livrées : code, commits, tests nommés, jumeaux, appelants ; deux écarts S2 prouvés par sonde.
- **Non couvert.** Les 7 tâches déjà cochées (ALEC17, ALEC30 à ALEC35) n'ont pas été relues ; les 8 tâches ouvertes non
  plus. Aucun test Django, FastAPI ou front lancé (la preuve des tests est la CI de `main`) ; statut CI de la livraison
  déduit du merge ; tests front et schéma OpenAPI des nouveaux refus non relus ; aucun rejeu navigateur.
- **Statut.** Deux écarts S2 : le groupe ne peut pas sortir du cycle sur cette contre-visite. La contre-visite de
  mi-parcours reste due à 50 % des tâches constructibles cochées, puis celle de clôture à 95 %.

## 7. Coût

- 1 vérificateur (opus, effort élevé) et 1 rédacteur ; aucun appel Fable.

<!-- verifie | groupe: ALEC | pct: 46 | ecarts_s1_s2: 2 -->
