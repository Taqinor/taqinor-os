# Vérifie APRF — contre-visite de clôture du groupe performance (X6), 04/11/2026

Commande `vérifie APRF` (METHODE §C.4.2, skill audit §5), jouée après `vérifie ADEV` (ordre par nombre de tâches cochées
décroissant : ADEV 97, APRF 38). La contre-visite précédente, du 11/10 (`docs/audits/2026-10-11-performance-verifie.md`),
était à mi-parcours ; le groupe compte depuis 38 tâches constructibles, toutes cochées (APRF24, 39, 40, 41 sont
`[BLOCKED]` : hors du compte).

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test nommé et le code de `main` avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est prouvé par une sonde exécutée en
transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `e62ca97aa` (PR #1260), re-fetch en début d'itération.
- **Registre.** X6 `performance`, groupe APRF, dossier `docs/audits/2026-10-08-performance.md`, 38/38 cochées.
- **Inventaire (déterministe).** 38 tâches APRF `[x]` dans 12 plans (TRANSVERSE 7, DEVIS 7, STOCK 4, DEPLOY 4, ANALYSE 3,
  CHANTIERS 2, FACTURATION 2, LEAD 2, SAV 2, DOCUMENTS, MOTEUR, PARAMETRES, SECURITE 1 chacun).
- **Échantillon (graine = SHA `e62ca97aa54a6d77e8eb9e2d68810226dd6e7c3d`).** Aucune S1/P0 au dossier ; 25 % du reste tirés
  par `random.Random(int(sha, 16)).sample` sur les ids triés (10 sur 38) : APRF6, 13, 15, 17, 18, 22, 27, 32, 34, 35.
  Total : **10 tâches**.
- **Pile.** Pile locale au code de `e62ca97aa` ; sonde jouée par `scripts/sonde.py`, transaction annulée, 0 mail.

## 1. Vérificateurs (4 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **7** | APRF6, 13, 15, 17, 18, 27, 35 |
| partiel | **3** | APRF22 (S3 + S4), APRF32 (S3), APRF34 (S2) |
| non-fait / faux / régression / déjà-présent | 0 | — |

Changements postérieurs jugés voulus, pas des régressions : refus 400 → 409 (ENF11 : APRF15) ; règle de CA réécrite par
AANA55 (APRF13, invariant « requêtes constantes » conservé) ; `engagement-bulk/` retiré par D-ACRM-6 (APRF22).

## 2. Sondes (1 REPRO)

| Sonde | Tâche | Observé (code de `main`, transaction annulée) |
|---|---|---|
| `docs/audits/sondes/APRF/C-APRF-VER-001.py` | APRF34 | tâche réelle jouée : job `done`, lien de la notification sur l'hôte **`minio:9000`** (= `MINIO_ENDPOINT`, interne en prod), `jobs-status/<id>/` ne sert que `result_file_key`, aucune URL servie par Django |

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu | Sonde |
|---|---|---|---|---|---|---|---|
| C-APRF-VER-001 | APRF43 | APRF34 | C10 | S2 | `backend/django_core/apps/stock/tasks.py::export_mouvements_xlsx_task` | export asynchrone (> 5 000 lignes) jamais téléchargeable (URL présignée MinIO interne) → lien de téléchargement signé servi par Django, comme l'export de réversibilité | `docs/audits/sondes/APRF/C-APRF-VER-001.py` |
| C-APRF-VER-002 | APRF44 | APRF22 | C8 | S3 | `backend/django_core/apps/crm/engagement.py::_signaux_pour_clients` | population de devis recopiée (version active) au lieu du sélecteur ventes (V1 signée en vigueur depuis ADVS37) → mêmes populations | STATIQUE |

**Constats S1-S2 : 1** (0 S1, 1 S2), reproduit. APRF45 clôt la section (acceptation en direct, jamais confiée à une lane).
Routage : APRF43, APRF45 dans `PLAN_AUDIT_STOCK.md` ; APRF44 dans `PLAN_AUDIT_LEAD.md`.

## 4. Critique de complétude

Aucun écart S1 ne subsiste : pas de critique Fable (METHODE §C.4.2), pas de seconde lentille (§B.5, réservée aux S1).

## 5. Optionnel (non déposé)

- APRF32 (S3, sans tâche : décision de budget) : la pente N+1 est gardée, mais le plafond absolu de la liste produits a été
  relevé de 12 à 24 (`docs/query-budgets.yml`, correctif CI de #890) ; le texte de la tâche dit 12. À trancher : revenir à
  12 (cartes société par page) ou entériner 24.
- APRF22 (S4) : seuil des dormants filtré en Python et non en base.
- APRF15 (S4) : liste vide → 409 avalé par `.catch(() => {})` dans `DevisListChrome.jsx`.
- APRF17 : retirer seulement `__paiement` du préchargement ne serait pas détecté (aucune `AffectationPaiement` en fixture).
- Jumeau non sondé de C-APRF-VER-001 : `publicapi` `BulkJobSerializer.get_resultat_url` (autre URL MinIO présignée).
- Rejeu P2.3.VENTES en échec sur l'oracle `action_requise_compteurs` de `docs/audits/sondes/APRF/C-APRF-ACC-VENTES.py`
  (+10 attendus par panier, +4 et +2 lus) : 14 des 20 devis sources clonés sont des versions remplacées
  (`is_active=False`), que `devis_en_jeu` exclut à dessein (ADEV45). Oracle dépendant des données, pas une régression.
- Rejeu P2.3.leads_N_3N en échec (15 requêtes à 30 leads, 20 à 90) : mesuré à 30 / 90 / 150 / 200 leads = 15 / 20 / 20 /
  20. Ce sont trois requêtes groupées (profil type de consommation, société, visites) qui n'apparaissent que si une ligne
  de la page porte la donnée : borné, pas une pente par ligne. L'oracle « ± 1 » de `aprf2.spec.js` est trop strict pour
  une page hétérogène.
- Dette d'acceptation APRF inchangée : APRF4, APRF23, APRF26 (`docs/audits/acceptation/APRF/_dette.yml`).

## 6. Couverture et non-couvert

- **Couvert.** 10 tâches sur 38 (25 %), commits, tests nommés (APRF27 rejoué par son vérificateur : 18 tests OK, mutants
  exécutés), code de `main`. Une sonde jouée. Rejeu en direct des specs `frontend/e2e/acceptation/aprf.spec.js` et
  `aprf2.spec.js` : enregistrement `docs/audits/acceptation/APRF/2026-11-04-e62ca97aa.md`, 8 étapes PASS sur 10
  (P4.3, tombée sur un délai de chargement au premier passage, rejouée PASS), verdict **FAIL** à cause de deux oracles
  de mesure (voir §5) ; aucun oracle qa-explorer en échec.
- **Non couvert.** Les 28 autres tâches ; aucun test Django exécuté par les vérificateurs.
- **Statut du registre.** Après ce dépôt : 38 cochées sur 41 constructibles (APRF43-45 ajoutées), contre-visite de clôture
  **avec 1 écart S1-S2** → statut calculé `audité` ; le cycle n'est pas sorti.

## 7. Coût

- 4 vérificateurs opus (effort élevé) : ≈ 0,7 M de jetons ; rédacteur partagé avec `vérifie ADEV`.
- Orchestrateur : échantillon, triage, 1 sonde écrite et jouée, rejeu des specs, dossier.
- H0 S0 O4 F0 · jetons sous-agents ≈ 0,7 M

<!-- verifie | groupe: APRF | pct: 100 | ecarts_s1_s2: 1 -->
