# Vérifie AFAC — contre-visite de CLÔTURE du groupe facturation (J5), 11/10/2026

*Ce dossier REMPLACE la contre-visite de mi-parcours du matin (pct 87, PR #960, conservée dans l'historique git) : le
groupe a franchi le seuil de clôture dans la journée, la contre-visite de clôture fait désormais foi pour le registre.*

Commande `vérifie AFAC` (clôture, METHODE §C.4.2-3). Le groupe a atteint **96 % cochées (81/84)** pendant la journée (des
sessions parallèles ont construit et recatégorisé des tâches AFAC) : `audit_registre.py --du` signalait « clôture (≥ 95 %),
pas vérifié depuis » — la contre-visite de mi-parcours (pct 87) ne couvrait pas le seuil. 2ᵉ contre-visite du groupe, même
jour. Groupe ARGENT.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `9f58de05f` (re-fetch en début d'itération). Branche de claim : `verifie-afac-cloture`.
- **Registre.** J5 `facturation`, groupe AFAC, propriétaire majoritaire `PLAN_AUDIT_FACTURATION.md` (68).
- **Historique.** Mi-parcours du matin : 24 ok + 6 partiel S3, 0 écart S1-S2, AFAC82 tranché (a) par le fondateur
  (PR #960). Écart de gravure AFAC102 déposé alors (couvre AFAC80-89).
- **Inventaire (déterministe).** 84 tâches AFAC, 81 `[x]`.
- **Échantillon (graine = SHA `9f58de05f`, distincte de celle du matin).** Toutes les P0/S1 cochées (13) + 25 % du reste
  (17 sur 68) = **30 tâches**. ~ la moitié diffèrent de l'échantillon de mi-parcours — la clôture couvre du terrain neuf.

## 1. Vérificateurs (30 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **28** | AFAC1, 5, 6, 12, 13, 16, 18, 19, 23, 25, 26, 27, 32, 40, 41, 42, 44, 47, 55, 57, 61, 63, 66, 67, 80, 87, 94, 96 |
| déjà-présent (conforme) | **1** | AFAC64 |
| partiel | **1** | AFAC81 (S3, déjà couvert par AFAC102) |
| non-fait / faux / régression | 0 | — |

**Constats S1-S2 : 0.**

Points saillants (argent, annulation, relevé) :

- **AFAC12/AFAC13 (annulation d'une facture qui porte de l'argent).** Serveur : 400 `directive_acompte_requise` sans
  directive, avances ventilées suivent le transfert, avoir actif bloquant (sauf avoir de ND). Écran : dialogue
  transférer/rembourser transmet la directive. Les deux moitiés de C-AFAC-002 (S1) confirmées corrigées.
- **AFAC5/AFAC6 (relevé bancaire).** Idempotence par empreinte + rang, session verrouillée, plus de date inventée ; revue
  ligne par ligne sans troncature, résolution hors candidats refusée 400. Tests comportementaux.
- **AFAC64 (déjà-présent CONFORME).** Tâche de recouvrement dont le texte autorise « déjà présent via ADEV35 »
  (`fetchAllPages` câblé) ; le commit n'ajoute que le test comportemental — pas un demi-travail.

## 2. Tests nommés

- 28 tâches ok + AFAC64 ont un test nommé **comportemental** (endpoints réels, montants stockés, Σ ≤ TTC). AFAC80/81/87 sont
  des DECISION (test absent légitime). Non rejoués localement (lecture seule) : vert de la CI de `9f58de05f`.

## 3. Sondes

Aucune sonde déposée : aucun écart S1-S2, et l'unique partiel (AFAC81) est une déviation d'emplacement documentaire déjà
tracée.

## 4. Écarts retenus

**Aucun NOUVEAU.** AFAC81 (partiel, S3) est le MÊME motif de gravure d'en-tête que les décisions AFAC80/82/84/86/87/88
relevées à mi-parcours : la décision D-AFAC-81 (a) est tranchée, enregistrée (`decisions.yml`, `decisions-audit-0810.md`) et
consommée par le code (`apps/ventes/views/paiement.py::annuler_saisie`), mais pas gravée dans le fichier nommé
`afac-decisions-fondateur.md`. **Déjà couvert par la tâche ouverte AFAC102** (`PLAN_AUDIT_FACTURATION.md`, « graver les 10
décisions AFAC80-89 »), qui inclut AFAC81 — aucune nouvelle tâche n'est déposée.

## 5. Optionnel (non déposé)

- AFAC61 : notes de leçons (3/7) d'un vérificateur sans divergence comportementale.

## 6. Couverture et sortie de cycle

- **Couvert.** 30 tâches sur 81 cochées (toutes les P0/S1 + 25 %), échantillon disjoint à ~50 % de celui du matin.
- **Non couvert.** Les 51 autres tâches cochées ; aucun aller-retour en direct (lecture seule) — l'acceptation est AFAC99.
- **Statut du registre.** Après ce dépôt : 81/84 cochées (96 % ≥ 95 = `construit`), contre-visite de **clôture sans écart
  S1-S2** (pct 96). Combinée à la contre-visite de mi-parcours également à **zéro écart S1-S2**, cela fait **deux
  contre-visites consécutives à zéro S1-S2 → SORTIE DU CYCLE** (METHODE §C.4.3) : AFAC est le premier groupe à atteindre
  `vérifié` stable cette campagne.

## 7. Coût

- 30 vérificateurs opus (effort élevé) : **≈ 2,53 M de jetons**, 518 appels d'outil, ≈ 46 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe (graine de clôture), triage des 30 verdicts, contrôle qu'AFAC81 est couvert par
  AFAC102, rédaction.

<!-- verifie | groupe: AFAC | pct: 96 | ecarts_s1_s2: 0 -->
