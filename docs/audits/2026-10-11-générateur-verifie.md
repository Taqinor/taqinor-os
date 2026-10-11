# Vérifie AGNR — contre-visite de clôture du groupe générateur (D4), 11/10/2026

Commande `vérifie AGNR` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**40 tâches cochées sur 44** constructibles (**90 %**) ; la contre-visite (proche clôture, ≥ 50 %) est due, première du
groupe. 11ᵉ de la boucle (ordre par nombre de tâches cochées décroissant). Groupe GÉNÉRATEUR : l'écran de création de devis
et son miroir JS (`solar.js`) ; vérificateurs attentifs au « jamais snapper un nombre tapé » et à la parité écran ↔ moteur.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `db25ecd4c` (re-fetch en début d'itération). Branche de claim : `verifie-agnr`.
- **Registre.** D4 `générateur`, groupe AGNR, propriétaire majoritaire `PLAN_AUDIT_GENERATEUR.md` (24) + devis (8) + transverse (4).
- **Décisions gravées.** D-AGNR-1 (deux factures hiver/été → `factures_hiver_ete`, étiqueté « Estimation ») ; AGNR43 =
  retirer le curseur « Consommation diurne ».
- **Inventaire (déterministe).** 44 tâches AGNR, 40 `[x]`.
- **Échantillon (graine = SHA `db25ecd4c`).** Toutes les P0/S1 cochées (8) + 25 % du reste (8 sur 32). Total : **16 tâches**.

## 1. Vérificateurs (16 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **12** | AGNR1, 5, 8, 10, 12, 13, 14, 16, 20, 26, 40, 44 |
| partiel | **4** | AGNR15 (S2), AGNR4 (S3), AGNR17 (S3), AGNR43 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1 : 0.** Pas de critique Fable (réservée aux écarts S1 restants).

Points saillants des tâches jugées ok (jamais-snap, parité, contrat) :

- **AGNR1 (prix de liste HT).** L'endpoint renvoie `unite='HT'`, le prix vient de `LignePrixListe.prix_unitaire` sans
  `×(1+TVA)` ; contrat `prix_applicable.json` aligné, test comportemental sur données réelles.
- **AGNR5 (contrat `factures_client.json`).** Clé écran `factures_hiver_ete` conforme à D-AGNR-1 ; série en marches
  recalculée depuis le code serveur réel (pas inventée) ; consommé par AGNR6/AGNR34 (PACT11 @after honoré).
- **AGNR8 (jamais snapper).** Les nombres d'en-tête sont normalisés à 2 décimales (arrondi demi-sup sur texte décimal,
  BigInt) AVANT l'envoi, évitant le 400 du `DecimalField(5,2)` ; une valeur déjà propre repart telle que tapée.

## 2. Tests nommés

- Les 12 tâches jugées ok ont un test nommé **présent et comportemental** (assert sur le corps envoyé / la parité). Les
  mentions de leçons sur des tâches ok (AGNR8/10/14/20/26) sont des notes sans divergence — verdict ok. Non rejoués
  localement (lecture seule) : raisonnés par lecture ; vert de la CI de `db25ecd4c`.

## 3. Sondes

Aucune sonde déposée pendant la contre-visite (lecture seule, sans pile). L'écart S2 AGNR15 porte sur un risque de chiffre
client (unité des listes de prix) : sa preuve (lecture prod + garde de round-trip) est portée par la tâche de correction
AGNR48.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Suite |
|---|---|---|---|---|---|
| AGNR46 | C-AGNR-VER-001 | AGNR4 + AGNR43 | S3 | D-AGNR-1/D-AGNR-2 tranchées dans `decisions.yml` mais l'en-tête « Décisions gravées » du groupe reste un marque-place « à graver ici » ; fichier `agnr-decisions-fondateur.md` consolidé dans `decisions-audit-0810.md` | tâche v3 docs-only (`PLAN_AUDIT_GENERATEUR.md`) |
| AGNR47 | C-AGNR-VER-002 | AGNR17 | S3 | test n'exerce que les champs/bandeau, ni la CLAUSE PERSISTANCE (save→reopen→aucune facture héritée) ni le corps envoyé | tâche v3 (`PLAN_AUDIT_GENERATEUR.md`) |
| AGNR48 | C-AGNR-VER-003 | AGNR15 | S2 | correctif HT→TTC juste, mais la clause de contrôle de risque (lecture prod `LignePrixListe` + décision fondateur sur l'unité + gravure) non exécutée ; une liste saisie en TTC gonflerait de 20 % (risque atténué par l'étiquette HT d'AGNR10, non gravé) | tâche v3 (`PLAN_AUDIT_GENERATEUR.md`, garde de round-trip + gravure + lecture prod en acceptation) |

**Constats S1 : 0.** AGNR15 est S2 (risque étroit, étiquette « Prix unitaire HT » d'AGNR10 + contrat `unite:HT` l'atténuent) ;
AGNR reste hors `vérifié` tant qu'AGNR48 n'est pas construit.

## 5. Optionnel (non déposé)

- Les décisions AGNR4/AGNR43 sont le même motif de gravure d'en-tête que les décisions AFAC/ACHT — consolidées ici dans
  AGNR46.
- AGNR8/14/20 : notes de leçons des vérificateurs sans divergence comportementale.

## 6. Couverture et non-couvert

- **Couvert.** 16 tâches sur 40 cochées (toutes les P0/S1 + 25 %). Commits, tests nommés, code écran + miroir JS, contrats.
- **Non couvert.** Les 24 autres tâches cochées ; aucun aller-retour en direct (lecture seule, sans pile) — la preuve live
  du groupe est AGNR42 (acceptation).
- **Statut du registre.** Après ce dépôt : 40/44 cochées (90 %), contre-visite avec **1 écart S2 + 3 écarts S3** déposés en
  tâches (0 écart S1). La clôture stricte (≥ 95 %) et la sortie du cycle restent dues ; AGNR ne sera `vérifié` qu'après
  construction + re-vérification d'AGNR48.

## 7. Coût

- 16 vérificateurs opus (effort élevé) : **≈ 1,45 M de jetons**, 296 appels d'outil, ≈ 30 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 16 verdicts, lecture des évidences AGNR15/17, rédaction.

<!-- verifie | groupe: AGNR | pct: 90 | ecarts_s1_s2: 1 -->
