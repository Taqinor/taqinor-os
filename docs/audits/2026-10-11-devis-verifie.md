# Vérifie ADEV — contre-visite mi-parcours du groupe devis (J1b), 11/10/2026

Commande `vérifie ADEV` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**60 tâches cochées sur 70** constructibles (**85 %**) ; la contre-visite de **mi-parcours** (≥ 50 %) est due, première du
groupe. 6ᵉ de la boucle (ordre par nombre de tâches cochées décroissant) après ASAV, AFAC, ACHT, AMOT, APAR.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `296e549f6` (re-fetch en début d'itération). Branche de claim : `verifie-adev`.
- **Registre.** J1b `devis`, groupe ADEV, propriétaire majoritaire `PLAN_AUDIT_DEVIS.md` (apps/ventes côté Devis).
- **Inventaire (déterministe).** 70 tâches ADEV, 60 `[x]`.
- **Échantillon (graine = SHA `296e549f6`).** Toutes les P0/S1 cochées (4) + 25 % du reste (14 sur 56). Total :
  **18 tâches**.

## 1. Vérificateurs (18 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out. Deux agents (ADEV50, ADEV51) sont tombés sur
une erreur API en première passe et ont été rejoués à l'identique (2ᵉ workflow) : les deux reviennent « ok ».

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **17** | ADEV1, 2, 8, 10, 18, 19, 21, 24, 25, 27, 29, 30, 33, 41, 49, 50, 51 |
| partiel | **1** | ADEV28 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1-S2 : 0.** Pas de critique Fable (réservée aux écarts S1).

Points saillants des tâches jugées ok (statut, parité chiffre, signature) :

- **ADEV1 / ADEV2 (contrats PACT10).** `devis_refuser.json` et `proposal_accept.json` déposés seuls (aucun code),
  `motif` validé par la source réelle `crm.services.motif_refus_valide`, codes 409 en liste fermée, tests qui parsent le
  JSON réel.
- **ADEV10 (taux d'acceptation ≤ 100 %).** Dénominateur = envoyés de la période (`devis_en_jeu`), numérateur sous-ensemble
  du même queryset → ≤ 100 % garanti ; l'ancien `400 %` (envoyés encore ouverts) disparu. Test sur valeurs servies.
- **ADEV50 / ADEV51 (cumul 25 ans servi ; empreinte de signature).** Le cumul 25 ans est servi par le serveur option par
  option (plus de `×25` en JS) ; la signature exige `empreinte_contenu` (SHA256 du contenu visible) et refuse 409
  `empreinte_perimee` si le devis a changé entre lecture et signature — gardes câblées avant `accept_devis`, tests
  comportementaux (aucune `DevisSignature`, statut ENVOYE après refus).

## 2. Tests nommés

- Les 17 tâches jugées ok ont un test nommé **présent et comportemental** (assert sur l'état serveur / le résultat stocké).
  Non rejoués localement (lecture seule, sans pile) : raisonnés par lecture ; vert de la CI de `296e549f6`.

## 3. Sondes

Aucune sonde déposée : l'unique écart (ADEV28) est S3 (volet de test C&I affaibli), sans fuite argent/client active — le
volet pompage d'ADEV28 est, lui, comportemental et branché (écran + PDF + page publique).

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Suite |
|---|---|---|---|---|---|
| ADEV75 | C-ADEV-VER-001 | ADEV28 | S3 | volet C&I du test `test_ci_egal_total_ttc` non comportemental : assert seulement l'invariant pré-existant `option_totaux==total_ttc` + « sans lever », test-du-test faux → une régression C&I passe inaperçue | tâche v3 déposée (`PLAN_AUDIT_DEVIS.md`) |

**Constats S1-S2 : 0.**

## 5. Optionnel (non déposé)

- ADEV8 : la tâche annonçait un test `.mjs`, le fichier réel est `.jsx` (déviation de nom, test présent et comportemental).
- ADEV50 : un vérificateur signale une préoccupation de test (leçon 5) sans que le comportement diverge — jugé ok.

## 6. Couverture et non-couvert

- **Couvert.** 18 tâches sur 60 cochées (toutes les P0/S1 + 25 %). Commits, tests nommés, code de production, contrats.
- **Non couvert.** Les 42 autres tâches cochées ; aucun aller-retour en direct (lecture seule, sans pile).
- **Statut du registre.** Après ce dépôt : 60/70 cochées (85 %), contre-visite mi-parcours **sans écart S1-S2** (1 écart S3
  déposé en tâche). La clôture (≥ 95 %) et la sortie du cycle restent dues plus tard.

## 7. Coût

- 18 vérificateurs opus (effort élevé), dont 2 rejoués après erreur API : **≈ 1,70 M de jetons** (1,50 M + 0,20 M), 370
  appels d'outil. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 18 verdicts, reprise des 2 agents tombés, lecture de l'évidence
  ADEV28, rédaction.

<!-- verifie | groupe: ADEV | pct: 85 | ecarts_s1_s2: 0 -->
