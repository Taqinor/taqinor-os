# Vérifie APAR — contre-visite mi-parcours du groupe parametres (X3), 11/10/2026

Commande `vérifie APAR` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**61 tâches cochées sur 67** constructibles (**91 %**) ; la contre-visite de **mi-parcours** (≥ 50 %) est due, première du
groupe. 5ᵉ de la boucle (ordre par nombre de tâches cochées décroissant) après ASAV, AFAC, ACHT, AMOT.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `296e549f6` (re-fetch en début d'itération). Branche de claim : `verifie-apar`.
- **Registre.** X3 `parametres`, groupe APAR, propriétaire majoritaire `PLAN_AUDIT_PARAMETRES.md` (apps/parametres).
- **Décisions gravées.** D-APAR-1/2 : `tva_standard` unique source de TVA ; bouton « Par défaut » retiré ; écran
  Approbations retiré, `discount_approval_threshold` seul réglage.
- **Inventaire (déterministe).** 67 tâches APAR, 61 `[x]`.
- **Échantillon (graine = SHA `296e549f6`).** Toutes les P0/S1 cochées (2) + 25 % du reste (15 sur 59). Total :
  **17 tâches**.

## 1. Vérificateurs (17 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out même répertoire (aucun worktree).

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **17** | APAR3, 4, 5, 7, 13, 15, 17, 19, 22, 23, 24, 26, 33, 39, 47, 50, 65 |
| partiel / non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1-S2 : 0.** Pas de critique Fable. Aucune tâche v3 `ÉCARTS` à déposer.

Points saillants des tâches jugées ok (réglage unique, scoping société, persistance) :

- **APAR3 (purge d'audit au plancher).** `purge_company_audit` passe par `effective_retention_days` (plancher
  `AUDIT_RETENTION_FLOOR_DAYS=365`), journalise une trace au nom de l'admin, re-raise l'erreur ; endpoint scopé société
  côté serveur. Test comportemental sur lignes conservées/supprimées + trace.
- **APAR4 (tolérance tarifaire = devis).** `_selective_price` lit la tranche par comparaison directe sur `effective_tiers`,
  identique au chemin devis pour toute tolérance (plus de double décalage des bornes). Test compare au vrai devis, 0 mock.
- **APAR5 (toute écriture de réglage exige `parametres_modifier`).** Patron `get_permissions` lecture=IsAnyRole /
  écriture=[tier + droit] sur les 6 viewsets ; rôles réels du registre (403 pour 3 rôles, 200 Directeur) ; objet serveur
  inchangé après refus.
- **APAR7 (prédicat d'état métier unique).** `engine.motif_etat_metier` branché sur les 4 appelants (signals, 2 sweeps,
  run_approved) ; une facture annulée/soldée/payée-entre-temps n'est plus relancée. Test compte des `AutomationRun`
  persistés, pas des espions.

## 2. Tests nommés

- Les 17 tâches ont un test nommé **présent et comportemental** (assert sur l'état serveur / le résultat stocké, pas espion
  ni regex). Non rejoués localement (lecture seule, sans pile) : raisonnés par lecture ; vert de la CI de `296e549f6`.

## 3. Sondes

Aucune sonde déposée : aucun écart retenu. Les clauses persistance/multi-société/réglage-unique des tâches échantillonnées
ont été jugées tenues par lecture du code de production (scoping `company`, source unique de réglage, re-lecture identique).

## 4. Écarts retenus

**Aucun.** 17/17 ok, 0 S1-S2, 0 S3.

## 5. Optionnel (non déposé)

- Néant de significatif : aucun verdict n'a signalé de leçon violée.

## 6. Couverture et non-couvert

- **Couvert.** 17 tâches sur 61 cochées (toutes les P0/S1 + 25 %). Commits, tests nommés, code de production.
- **Non couvert.** Les 44 autres tâches cochées ; aucun aller-retour en direct (lecture seule, sans pile).
- **Statut du registre.** Après ce dépôt : 61/67 cochées (91 %), contre-visite mi-parcours **sans écart S1-S2**. La clôture
  (≥ 95 %) et la sortie du cycle (deux contre-visites consécutives à zéro S1-S2) restent dues plus tard.

## 7. Coût

- 17 vérificateurs opus (effort élevé) : **≈ 1,37 M de jetons**, 317 appels d'outil, ≈ 20 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 17 verdicts, rédaction.

<!-- verifie | groupe: APAR | pct: 91 | ecarts_s1_s2: 0 -->
