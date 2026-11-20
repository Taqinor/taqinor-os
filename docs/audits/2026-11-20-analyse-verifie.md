# Vérifie AANA — contre-visite des correctifs de l'unité X7 « analyse », 20/11/2026

<!-- verifie | groupe: AANA | pct: 100 | ecarts_s1_s2: 0 | faits: 90 -->

Commande `loop audit` (20/11). La contre-visite du 10/11 (`docs/audits/2026-11-10-analyse-verifie.md`) laissait un écart
S2 du 04/11 ouvert : l'agent SQL à qui le prompt prescrivait la somme `quantite × prix_unitaire` des lignes d'un devis
comme montant (AANA81, alors bloquée sur sa preuve en direct). `audit_registre.py --du` la déclare due : 90 tâches cochées
sur 90 constructibles, « écarts S1-S2 du 2026-11-10 tous cochés ». Rien n'a été construit ni déployé ; aucune base, aucun
conteneur, aucune production n'a été lu.

## 0. Préconditions

- **SHA.** `origin/main` = `a923179a4` (PR #1496). Branche de claim : `verifie-aana-2011`.
- **Cochées depuis le 10/11 : 3.** AANA81 (`679ee1193`, acceptation `e3b0360b6`, `31499634a`), AANA91 (`550575d04`,
  acceptation `55da74e19`) et AANA90 (acceptation du groupe, `c90455638`).
- **Échantillon : les 3** (contre-visite des correctifs, METHODE §C.4-6).
- **Méthode.** Un vérificateur frais (opus / high, même répertoire) : commits, code servi, liste des tests du job
  `fastapi-security` de `.github/workflows/ci.yml`, enregistrements et spécifications d'acceptation, champs des modèles
  relus par `ast`, deux sondes hôte jouées. Aucun test lancé (sur l'hôte, `sqlglot` et `fastapi` manquent : les deux tests
  nommés y sont sautés ; la CI de chaque PR échoue sur un saut, `verifier_sortie_unittest.py`).

## 1. Verdicts

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **2** | AANA81, AANA91 |
| partiel | **1** | AANA90 |
| non-fait / faux / régression / déjà-présent | **0** | — |

**Écart S2 d'origine (AANA81) : fermé.** La puce « Devis » de `_AGENT_PREFIX` (`backend/fastapi_ia/app/services/sql_agent_service.py`)
ne prescrit plus la somme : elle renvoie à la fiche du devis dans l'ERP, et le chiffre d'affaires facturé à
`SUM(ventes_facture.total_ht_stocke)`. Ce préfixe sert les deux chemins (Claude et Groq, `_contenu_systeme`). La spec en
direct `frontend/e2e/acceptation/aana7.spec.js` joue le vrai agent sous `sql_agent_ro` et lit le journal des requêtes
Postgres : aucune requête `ventes_lignedevis` avec `quantite*prix_unitaire` dans un ordre ou dans l'autre, aucun `SUM(` sur
`ventes_lignedevis`, ni 2 500 ni 3 000 dans la réponse, renvoi à la fiche (PASS `2026-11-17-d0ffddeae`, précédé du 13/11).
Aucun autre prompt de `backend/fastapi_ia` (copilote, `manuel.md`, métriques gouvernées) ne fait additionner des lignes de
devis ou de facture (grep `prix_unitaire`, `quantite`, `total_ht`, `SUM`, `montant`).

**AANA91 : ok dans son périmètre.** `ventes_devis` et `ventes_lignedevis` ne décrivent plus que des colonnes réelles (champs
de `Devis` / `LigneDevis` relus par `ast`). Le jumeau `ventes_facture` / `ventes_lignefacture`, que la tâche jugeait sans
écart, en garde deux inventées (§4).

**AANA90 : partiel.** La clause « fini quand » tient : la dette gelée du groupe ne garde qu'AANA30, l'enregistrement
`2026-11-19-1773d1c7a` est PASS sur P1-P4, société B comprise. Mais la contre-épreuve sur la base `32375fe65` n'a pas été
jouée (`base_verdict` nul sur les 4 étapes) : le DONE LOG le déclare (« NON jouée … à rejouer si exigé »). Rien ne montre
que le rejeu aurait échoué avant les correctifs (L7).

## 2. Tests nommés

| Tâche | Test | Joué par la CI de chaque PR | Casse si on revient en arrière |
|---|---|---|---|
| AANA81 | `backend/fastapi_ia/tests/test_eval_harness.py::EvalHarnessTests::test_somme_des_lignes_de_devis_signalee` | oui (job `fastapi-security` depuis `12dfbbac9`) | oui (`assertNotIn("SUM(ventes_lignedevis")` sur l'ancien texte) |
| AANA91 | `backend/fastapi_ia/tests/test_sql_agent_endpoint.py::RelevantTableSelectionTests::test_descriptions_devis_sans_colonne_inexistante` | oui | oui (ni « montant » ni « numero ») |
| AANA90 | sans objet (acceptation) | — | — |

La note du 10/11 (« test d'AANA81 joué seulement la nuit ») est résolue. Le résultat d'un run CI précis n'a pas été relu.

## 3. Sondes

| Sonde | Tâche | Verdict | Observé (hôte, `a923179a4`) |
|---|---|---|---|
| `C-AANA-VER4-400.py` (neuve) | AANA81 | prompt : réfuté ; banc : repro | `prefix_prescrit_somme: false`, `prefix_renvoie_fiche: true` ; le motif `_SOMME_LIGNES` du banc d'évaluation ne repère ni `prix_unitaire * quantite`, ni la remise en tête, ni un `CAST` (optionnel, §5) |
| `C-AANA-VER4-401.py` (neuve) | AANA91 (jumeau) | **REPRO** | inventés : `ventes_facture` → `numero` ; `ventes_lignefacture` → `montant` ; devis propres |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-AANA-VER4-401 | AANA91 (jumeau) | S3 | Le dictionnaire `_TABLE_DESCRIPTIONS` de `backend/fastapi_ia/app/services/sql_agent_service.py` décrit `ventes_facture` avec « numero » (le champ est `reference`, `backend/django_core/apps/facturation/models.py::Facture`) et `ventes_lignefacture` avec « montant » (aucune colonne de montant, `backend/django_core/apps/facturation/models.py::LigneFacture`) ; même dictionnaire et même écran Paramètres › IA qu'AANA91. Aucune requête fausse établie : le schéma remis au modèle vient de la base. | `C-AANA-VER4-401.py` (REPRO) | AANA92 |

## 5. Optionnel (non déposé)

- **Contre-épreuve d'AANA90 (C-AANA-VER4-402, STATIQUE).** `docs/audits/acceptation/AANA/2026-11-19-1773d1c7a.results.json` porte
  `base_verdict: null` sur ses 4 étapes. À rejouer (`aana8.spec.js` sur `32375fe65`, base restaurée par incrément : la
  migration à froid a échoué au run 44630935165) si le fondateur l'exige ; déclarée par la vague, sans effet sur le code.
- **Banc d'évaluation (sonde VER4-400).** `_SOMME_LIGNES` dépend de l'ordre des facteurs (`SUM(l.prix_unitaire *
  l.quantite)`, remise en tête, `CAST(l.quantite AS numeric) * l.prix_unitaire` non repérés). La spec en direct, elle,
  couvre les deux ordres ; la tâche ne nommait que `quantite * prix_unitaire` : renforcement, pas écart.
- Le cas du banc note le `gold_sql` écrit à la main, pas la sortie du modèle ; seule l'acceptation en direct teste le
  modèle, sur un rejeu non déterministe.
- La spec en direct d'AANA81 utilise un devis à une option, pas le devis à deux options du constat d'origine ; l'invariant
  vérifié (aucune requête de somme de lignes) n'en dépend pas.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 3 tâches cochées depuis le 10/11 : commits, code servi, tests nommés et leur place dans la CI,
  enregistrements et specs d'acceptation, jumeaux par grep, champs des modèles par `ast` ; deux sondes hôte.
- **Non couvert.** Aucun test lancé, aucun rejeu sur pile ; les 87 autres tâches cochées (relues par les contre-visites
  du 04/11 et du 10/11).
- **Sortie de cycle.** L'écart S2 du 04/11 est fermé et aucun écart S1-S2 nouveau n'est déposé (une tâche S3, AANA92).
  Compteur des `vérifie` consécutifs à zéro S1-S2 : **1**. Il en faut un second pour sortir du cycle.

## 7. Coût

H0 S0 O1 F0 · jetons sous-agents ≈ 0,17 M (un vérificateur opus seul). Aucun appel Fable : aucun S1.
