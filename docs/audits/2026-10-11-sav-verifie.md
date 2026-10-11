# Vérifie ASAV — contre-visite mi-parcours du groupe sav (J4), 11/10/2026

Commande `vérifie ASAV` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**84 tâches cochées sur 90** constructibles (**93 %**) ; la contre-visite de **mi-parcours** (≥ 50 %) est due. C'est la
première contre-visite du groupe. Ordre de la boucle : parmi les 13 groupes dus, ASAV a le plus de tâches cochées (84),
donc traité en premier (règle fondateur 11/10 « commencer par les groupes qui ont le plus de tâches faites » — METHODE
§C.4.2 amendée dans cette PR).

Pour chaque tâche de l'échantillon, on rapproche le texte de la tâche, le ou les commits et le test rouge nommé, avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Les écarts confirmés seraient déposés en tâches v3 dans le
plan du propriétaire des fichiers ; il n'y en a aucun. La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a
rien écrit (lecture seule, sans pile locale).

## 0. Préconditions

- **SHA.** `origin/main` = `7689149ca` (PR #955). Branche de claim : `verifie-sav`.
- **Registre.** J4 `sav`, groupe ASAV, dossier `docs/audits/2026-10-07-…` (via `audit_registre.py`). Propriétaire des
  fichiers des tâches : apps/sav → `PLAN_AUDIT_SAV.md`.
- **Inventaire (déterministe).** 90 tâches ASAV, 84 `[x]`, 6 non cochées (hors échantillon).
- **Échantillon (graine = SHA `7689149ca8c831ce8a4f011c7f70aa8281c76683`).** Toutes les P0/S1 cochées (ASAV2, ASAV3,
  ASAV4, ASAV5, ASAV6, ASAV7, ASAV95) + 25 % du reste tirées par `random.Random(sha).sample` (19 sur 77). Total :
  **26 tâches**, toutes dans `PLAN_AUDIT_SAV.md`.

## 1. Vérificateurs (26 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out même répertoire (aucun worktree).

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **26** | toutes |
| partiel / non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1-S2 : 0.** Pas de critique Fable (réservée aux écarts S1 restants). Aucune tâche v3 `ÉCARTS` à déposer.

Points saillants des tâches jugées ok (argent / client / persistance) :

- **ASAV2 (P0, S1 — une seule porte de facturation SAV).** `services.decision_facturation` est le service unique ;
  `views.generer_facture` et `views.facturer` passent tous deux par `_facturer_ticket` → vrai alias. Récidive
  `non_facturable` → 403 sauf override d'un responsable ; contrat/garantie → ligne à 0. Test comportemental
  (`tests_asav2_decision_facturation.py`) lit la `Facture` stockée et asserte `prix_unitaire == 0`, 0 facture après refus.
- **ASAV3 (P0, S1 — écran : un seul bouton « Facturer »).** `TicketsPage.jsx` ne rend plus qu'un bouton ; « Générer
  facture »/`genererFacture` supprimés (0 occurrence). Override visible aux seuls responsable/admin. Test jsx sur l'état
  serveur en mémoire (pas les args).
- **ASAV4 / ASAV5 (couverture & quotas de contrat).** Couverture jugée à `date_reference_couverture` (= date d'ouverture,
  champ stocké immuable — persistance tenue à la relecture). `droits_restants` filtre `annule=False`, exclut le ticket
  évalué, compte par antériorité ; 1ᵉʳ ticket CONTRAT, 2ᵉ FACTURABLE une fois le quota épuisé. Tests comportementaux sur
  les valeurs renvoyées, test-du-test valide.
- **ASAV91/92/95 (DECISION, test absent légitime).** Décisions fondateur du 08/10 (D-ASAV-2/3/6) consignées dans
  `docs/audits/decisions.yml` + `docs/claude-memory/decisions-audit-0810.md`, indexées dans `MEMORY.md`, recopiées dans
  ASAV4/11/73/74, et **consommées par du code vivant** (`models.Ticket.date_reference_couverture`,
  `serializers_maintenance` champs récurrents retirés). Aucune source parquée/mockée (leçon 3 OK).

## 2. Tests nommés

- Les tests nommés des tâches échantillonnées sont présents et **comportementaux** (assert sur l'état serveur / la réponse
  réelle, pas espion ni regex sur le source) pour les 23 tâches de code ; les 3 tâches DECISION (ASAV91/92/95) n'attendent
  aucun test.
- Non rejoués localement (lecture seule, pas de pile) : raisonnés par lecture ; vert de la CI de `7689149ca`.

## 3. Sondes

Aucune sonde Django déposée : aucun écart retenu. Les clauses argent/client/persistance des tâches échantillonnées (ligne
à 0, une seule facture, couverture à la date d'ouverture, quotas) ont été jugées tenues par lecture du code de production
réellement touché.

## 4. Écarts retenus

**Aucun.** 26/26 ok, 0 S1-S2, 0 S3.

## 5. Optionnel (non déposé)

- **Nom de fichier des décisions (ASAV91/92/95).** La clause Then nommait `docs/claude-memory/sav-decisions-fondateur.md`,
  qui n'existe pas ; le fondateur a consolidé les décisions du 08/10 dans `decisions-audit-0810.md` (traçable, indexé,
  recopié). Déviation cosmétique voulue, pas un défaut.
- **ASAV2.** La restriction « override réservé au responsable » existe dans le code mais n'est pas couverte par un test
  avec un acteur non-responsable côté backend (le front la teste côté technicien).

## 6. Couverture et non-couvert

- **Couvert.** 26 tâches sur 84 cochées (toutes les P0/S1 + 25 % du reste). Commits, tests nommés, code de production.
- **Non couvert.** Les 58 autres tâches cochées ; les 6 non cochées ; aucun aller-retour en direct (lecture seule, sans
  pile) — la preuve en direct relève de l'acceptation du plan-run, pas de cette contre-visite.
- **Statut du registre.** Après ce dépôt : 84/90 cochées (93 %), contre-visite mi-parcours sans écart S1-S2. La sortie du
  cycle (METHODE §C.4.3) demande deux contre-visites consécutives à zéro S1-S2 ; la contre-visite de clôture (≥ 95 %)
  reste due plus tard.

## 7. Coût

- 26 vérificateurs opus (effort élevé) : **≈ 2,09 M de jetons**, 448 appels d'outil, ≈ 31 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 26 verdicts, contrôle des 3 verdicts « test absent », rédaction.

<!-- verifie | groupe: ASAV | pct: 93 | ecarts_s1_s2: 0 -->
