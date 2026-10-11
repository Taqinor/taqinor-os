# Vérifie AFAC — contre-visite mi-parcours du groupe facturation (J5), 11/10/2026

Commande `vérifie AFAC` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**80 tâches cochées sur 91** constructibles (**87 %**) ; la contre-visite de **mi-parcours** (≥ 50 %) est due, première du
groupe. Ordre de la boucle : parmi les groupes dus, AFAC a le plus de tâches cochées après ASAV (règle fondateur 11/10,
METHODE §C.4.2). Groupe ARGENT : vérificateurs attentifs aux montants, TVA, acomptes/avoirs, multi-société.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en production (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `7ff9c6a3d` (re-fetch en début d'itération ; des sessions parallèles mergent en continu).
  Branche de claim : `verifie-afac`.
- **Registre.** J5 `facturation`, groupe AFAC, propriétaire majoritaire `PLAN_AUDIT_FACTURATION.md`.
- **Inventaire (déterministe).** 88 tâches AFAC relevées, 81 `[x]`.
- **Échantillon (graine = SHA `7ff9c6a3d337701538af28957ae018294e7d7ec1`).** Toutes les P0/S1 cochées (13) + 25 % du
  reste tirées par `random.Random(sha).sample` (17 sur 68). Total : **30 tâches**. Par fichier : FACTURATION 25, DEPLOY 2,
  TRANSVERSE 2, DEVIS 1.

## 1. Vérificateurs (30 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out même répertoire (aucun worktree).

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **24** | AFAC1, 5, 10, 12, 13, 21, 27, 28, 30, 33, 40, 41, 42, 43, 47, 51, 53, 57, 66, 67, 69, 70, 71, 96 |
| partiel | **6** | AFAC80, 82, 84, 86, 87, 88 (toutes DECISION, S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1-S2 : 0** (après résolution de l'écart AFAC82, §4). Pas de critique Fable (réservée aux écarts S1).

Points saillants des tâches jugées ok (argent / persistance) :

- **AFAC5 (relevé bancaire idempotent).** `paiement_import._parse_date` renvoie None sur date non reconnue (plus de repli
  `_date.today()`), idempotence par empreinte normalisée (date|montant 2 déc.|ref|libellé) + rang d'occurrence,
  `select_for_update` + `consomme_at`, contrainte d'unicité réelle. Test comportemental sur l'état stocké, rouge d'abord
  prouvé.
- **AFAC12 (annulation d'une facture qui porte de l'argent).** `FactureViewSet.annuler` refuse 400
  `directive_acompte_requise` sans `save` quand `net_acompte > 0` ; `transferer` re-pointe les `AffectationPaiement` ;
  net = `Facture.montant_paye` (ATOT7, exclut les paiements rejetés) ; multi-société et même-devis vérifiés ; `avoir_actif`
  exclut l'avoir de la note de débit. Jumeau de test réécrit 200→400.
- **AFAC1 (contrat PACT10).** `facture_annulation.json` partagé seul sur `main` ; `argent_rattache` renvoie exactement les
  5 clés {paiements, affectations, notes_debit, retenues, avoirs_actifs} en `Decimal`, fidèle au contrat.
- **AFAC10 (écran : un seul bouton encaisser).** Les 3 sites d'action lisent le champ serveur `encaissable` (plus de règle
  JS locale) ; jumeaux corrigés dans le même commit ; source serveur réelle (pas de mock).

## 2. Tests nommés

- Les 24 tâches de code jugées ok ont un test nommé **présent et comportemental** (assert sur l'état serveur / le montant
  stocké, pas espion ni regex). Les 6 tâches DECISION n'attendent aucun test (test absent légitime).
- Non rejoués localement (lecture seule, sans pile) : raisonnés par lecture ; vert de la CI de `7ff9c6a3d`.

## 3. Sondes

Aucune sonde déposée : aucun écart argent/client/persistance retenu. Les clauses argent des tâches échantillonnées
(Σ factures ≤ TTC, net d'acompte, avoirs, idempotence du relevé) ont été jugées tenues par lecture du code de production.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Suite |
|---|---|---|---|---|---|
| AFAC102 | C-AFAC-VER-001 | AFAC80/82/84/86/87/88 | S3 | clause de gravure non tenue : les 10 décisions AFAC80-89 sont tranchées dans `decisions.yml` mais l'en-tête les liste encore sous « OUVERTES » ; fichier nommé `afac-decisions-fondateur.md` consolidé dans `decisions-audit-0810.md` | tâche v3 docs-only déposée dans `PLAN_AUDIT_FACTURATION.md` |

**Écart AFAC82 (code ↔ décision), résolu par le fondateur dans cette PR.** La décision enregistrée D-AFAC-82 valait (b)
« GARDER la pile mandat de prélèvement visible et inerte », mais le commit mergé **AFAC19 (`30ca6a67e`, 09/10)** l'avait
**parquée** (option a : écran/menu/route/viewset/service retirés) en citant cette même décision. Soumis au fondateur
(`AskUserQuestion`, 11/10) : **réponse (a) — garder parquée, le code mergé fait foi** (aucun client n'est prélevé
aujourd'hui, un écran mandat visible induit le commercial en erreur). `decisions.yml` (D-AFAC-82 → a, 11/10),
`decisions-audit-0810.md` et l'annotation de la ligne AFAC82 ont été alignés sur (a) dans cette PR. Plus de contradiction,
donc **pas d'écart S2** et aucune tâche de build.

**Constats S1-S2 : 0.**

## 5. Optionnel (non déposé)

- AFAC10 : un 4ᵉ cas de test est une regex sur le source (accessoire, leçon 5 mineure) — les 3 autres sont comportementaux.
- Les 6 décisions échantillonnées ont toutes le même motif de « partiel » (gravure d'en-tête + nom de fichier consolidé),
  couvert d'un coup par AFAC102.

## 6. Couverture et non-couvert

- **Couvert.** 30 tâches sur 80 cochées (toutes les P0/S1 + 25 %). Commits, tests nommés, code de production, contrats.
- **Non couvert.** Les 50 autres tâches cochées ; aucun aller-retour en direct (lecture seule, sans pile).
- **Statut du registre.** Après ce dépôt : 80/91 cochées (87 %), contre-visite mi-parcours **sans écart S1-S2** (un écart
  S3 déposé en tâche). La clôture (≥ 95 %) et la sortie du cycle (deux contre-visites consécutives à zéro S1-S2, METHODE
  §C.4.3) restent dues plus tard.

## 7. Coût

- 30 vérificateurs opus (effort élevé) : **≈ 2,49 M de jetons**, 539 appels d'outil, ≈ 37 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 30 verdicts, vérification du commit AFAC19 vs décision AFAC82,
  question au fondateur, alignement de la décision, rédaction.

<!-- verifie | groupe: AFAC | pct: 87 | ecarts_s1_s2: 0 -->
