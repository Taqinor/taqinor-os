# Vérifie ACHT — contre-visite mi-parcours du groupe chantiers (J2), 11/10/2026

Commande `vérifie ACHT` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**79 tâches cochées sur 85** constructibles (**92 %**) ; la contre-visite de **mi-parcours** (≥ 50 %) est due, première du
groupe. 3ᵉ de la boucle (ordre par nombre de tâches cochées décroissant, règle fondateur 11/10) après ASAV puis AFAC.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `73bca1947` (re-fetch en début d'itération). Branche de claim : `verifie-acht`.
- **Registre.** J2 `chantiers`, groupe ACHT, propriétaire majoritaire `PLAN_AUDIT_CHANTIERS.md` (apps/installations).
- **Inventaire (déterministe).** 85 tâches ACHT, 79 `[x]`.
- **Échantillon (graine = SHA `73bca19471b8f53cfb9f3071c39269e1c9461a36`).** Toutes les P0/S1 cochées (6) + 25 % du
  reste (18 sur 73). Total : **24 tâches**.

## 1. Vérificateurs (24 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out même répertoire (aucun worktree).

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **21** | ACHT1, 2, 3, 8, 11, 15, 21, 22, 24, 27, 29, 35, 37, 44, 47, 49, 52, 66, 70, 72, 91 |
| partiel | **3** | ACHT53, ACHT57, ACHT90 (toutes S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1-S2 : 0.** Pas de critique Fable (réservée aux écarts S1).

Points saillants des tâches jugées ok (stock / persistance / parcours) :

- **ACHT1 (une vente = une sortie).** `quantite_deja_sortie_chantier` est la source unique (consommation terrain F11 +
  soldes de vente) ; le calcul local `deja_sorti` a disparu ; réactivation/V2/réservation/réception passent tous par elle ;
  test comportemental sur `MouvementStock`/`StockReservation` réels, idempotence du second « Installé ».
- **ACHT2 (machine d'états serveur).** `raison_machine_etats` refuse l'annulé et tout saut > 1 rang ; les 3 portes
  (PATCH/mise-en-service/avancer-étape) passent par `changer_statut_chantier` ; test relit l'état après refus.
- **ACHT8 (sélecteur de nomenclature).** Source unique `quantites_nomenclature_chantier` (gel BOM, repli devis, arrondi) ;
  `apps/stock` la lit via `selectors` (frontière M3 respectée) ; test ajoute une ligne intruse après gel et prouve qu'elle
  n'est pas vue.

## 2. Tests nommés

- Les 23 tâches de code jugées ok ont un test nommé **présent et comportemental** (assert sur l'état serveur / le DOM
  réel) ; la tâche DECISION ACHT91 n'attend aucun test.
- Non rejoués localement (lecture seule, sans pile) : raisonnés par lecture ; vert de la CI de `73bca1947`.

## 3. Sondes

Aucune sonde déposée : les 3 écarts sont S3 (couverture de test, jumeau front à faible matérialité, bookkeeping d'en-tête)
sans fuite argent/client/multi-société active — les gardes de production correspondantes existent et ont été lues.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Suite |
|---|---|---|---|---|---|
| ACHT101 | C-ACHT-VER-001 | ACHT53 | S3 | test non étendu aux champs entiers `*_id` inscriptibles (`instrument_id`) ; garde prod `validate_instrument_id` existe (pas de fuite) | tâche v3 déposée (`PLAN_AUDIT_CHANTIERS.md`) |
| ACHT102 | C-ACHT-VER-002 | ACHT57 | S3 | jumeau nommé non corrigé : le formulaire `mes` de `InstallationDetail` ne se resynchronise pas comme `fields` (matérialité faible) | tâche v3 déposée |
| ACHT103 | C-ACHT-VER-003 | ACHT90 | S3 | gravure non tenue : ACHT90/91/94/95 tranchées dans `decisions.yml` mais l'en-tête ACHT les liste encore sous « OUVERTES » | tâche v3 docs-only déposée |

**Constats S1-S2 : 0.**

## 5. Optionnel (non déposé)

- ACHT1 : le « Test-du-test » cite « remettre `release_reservations` » alors que le correctif réel est l'ajout de
  `solder_reservations_consommation_terrain` ; mécanisme et tests sains.
- ACHT90 : même motif de gravure d'en-tête que les décisions AFAC (voir `2026-10-11-facturation-verifie.md`, AFAC102) —
  traité ici par ACHT103 pour le groupe ACHT.

## 6. Couverture et non-couvert

- **Couvert.** 24 tâches sur 79 cochées (toutes les P0/S1 + 25 %). Commits, tests nommés, code de production.
- **Non couvert.** Les 55 autres tâches cochées ; aucun aller-retour en direct (lecture seule, sans pile).
- **Statut du registre.** Après ce dépôt : 79/85 cochées (92 %), contre-visite mi-parcours **sans écart S1-S2** (3 écarts
  S3 déposés en tâches). La clôture (≥ 95 %) et la sortie du cycle (deux contre-visites consécutives à zéro S1-S2) restent
  dues plus tard.

## 7. Coût

- 24 vérificateurs opus (effort élevé) : **≈ 1,96 M de jetons**, 412 appels d'outil, ≈ 32 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 24 verdicts, lecture des évidences ACHT53/57/90, rédaction.

<!-- verifie | groupe: ACHT | pct: 92 | ecarts_s1_s2: 0 -->
