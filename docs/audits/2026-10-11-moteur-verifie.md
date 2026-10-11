# Vérifie AMOT — contre-visite mi-parcours du groupe moteur (D2), 11/10/2026

Commande `vérifie AMOT` (METHODE §C.4.2, skill audit §5), déclenchée par `audit_registre.py --du` : le groupe compte
**66 tâches cochées sur 75** constructibles (**88 %**) ; la contre-visite de **mi-parcours** (≥ 50 %) est due, première du
groupe. 4ᵉ de la boucle (ordre par nombre de tâches cochées décroissant) après ASAV, AFAC, ACHT. Groupe RÈGLE #4 (le
moteur PDF vendoré `apps/ventes/quote_engine`) : vérificateurs attentifs à la parité chiffre PDF = écran = serveur, aux
traductions, au non-chemin-alternatif et à la non-fuite de `prix_achat`.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit (lecture seule, sans pile).

## 0. Préconditions

- **SHA.** `origin/main` = `b99ccea9c` (re-fetch en début d'itération). Branche de claim : `verifie-amot`.
- **Registre.** D2 `moteur`, groupe AMOT, propriétaire majoritaire `PLAN_AUDIT_MOTEUR.md` (apps/ventes/quote_engine).
- **Inventaire (déterministe).** 75 tâches AMOT, 66 `[x]`.
- **Échantillon (graine = SHA `b99ccea9c7a84216dced2251473534350234669f`).** Toutes les P0/S1 cochées (19) + 25 % du reste
  (12 sur 47). Total : **31 tâches**.

## 1. Vérificateurs (31 agents frais, opus, effort élevé, lecture seule, même répertoire)

Un vérificateur frais par tâche (jamais l'auteur), un seul workflow fan-out même répertoire (aucun worktree).

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **29** | AMOT8, 10, 11, 14, 15, 16, 17, 18, 19, 21, 28, 29, 30, 34, 35, 38, 44, 45, 47, 48, 49, 50, 59, 60, 61, 67, 69, 70, 72 |
| partiel | **2** | AMOT58 (S3), AMOT73 (S2) |
| non-fait / faux / régression / déjà-présent | 0 | — |

**Constats S1 : 0** (l'écart AMOT73 est jugé S2, voir §4). Pas de critique Fable (réservée aux écarts S1 restants).

Points saillants des tâches jugées ok (parité chiffre client, règle #4) :

- **AMOT8 / AMOT10 / AMOT11 (totaux imprimés = noyau).** Mono-option réseau+batterie recompose `_all_rows`/`display_total`
  sur la liste complète (batterie incluse) ; la variante après signature ne réécrit plus `display_total` ; un `taux_tva=0`
  explicite est préservé (`is not None`) pour les nouveaux rendus. Garde de classe AMOT48 (`DOC_TOTAL_IMPRIME_NE_NOYAU`)
  présente. Tests comportementaux sur full + onepage, `display_total == devis.total_ttc`.
- **AMOT14 (clé PDF `__apercu`).** Un rendu `persist=False` (aperçu, `/proposal`, e-mail) n'écrase pas le PDF mémorisé ;
  seul `persist=True` écrit `fichier_pdf` (jamais `statut` — règle #4). Test réel sur stockage patché.
- **Règle #4 vérifiée partout.** Aucun chemin PDF devis alternatif introduit ; `prix_achat`/marge absents du dict de rendu
  et de `/proposal` (commentaires d'interdiction + garde AMOT49 `DOC_RENDU_SANS_MARGE`).

## 2. Tests nommés

- Les 29 tâches jugées ok ont un test nommé **présent et comportemental** (assert sur les totaux rendus / le nombre de
  pages / le contenu du PDF, pas espion ni regex). Les tests de pages vivent dans `apps/ventes/tests/test_quote_engine*.py`.
- Non rejoués localement (lecture seule, sans pile) : raisonnés par lecture ; vert de la CI de `b99ccea9c`.

## 3. Sondes

Aucune sonde déposée pendant la contre-visite (lecture seule, sans pile). L'écart S2 AMOT73 porte sur un chiffre client
(critère C1) : sa preuve exécutable (sonde/test rouge-d'abord d'un devis 0 % rendu en premium) est portée par la tâche de
correction AMOT77 déposée au plan, conformément à la règle « pas de constat S1-S2 sans sonde » reportée sur le correctif.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Suite |
|---|---|---|---|---|---|
| AMOT77 | C-AMOT-VER-001 | AMOT73 | S2 | `generate_devis_premium.py::apply_quote_data` garde `float(data.get("taux_tva",20) or 20)` (whitelisté `A_CORRIGER`, pas corrigé) → un devis 0 % rendu en premium calcule 20 % ; le DONE LOG l'admet | tâche v3 déposée (`PLAN_AUDIT_TRANSVERSE.md`, multi-propriétaires moteur + deploy, @model opus) |
| AMOT78 | C-AMOT-VER-002 | AMOT58 | S3 | la déduction unique du rendement batterie ne couvre que le modèle HORAIRE ; le modèle factures/estimation reste BRUT (double comptage), commit AMOT58 « volet factures/estimation non traité » | tâche v3 déposée (`PLAN_AUDIT_TRANSVERSE.md`, multi-propriétaires moteur + devis, @atomique) |

**Constats S1 : 0.** AMOT73 est jugé S2 (le trigger est étroit — devis exonéré 0 % — et le chemin courant des totaux
vient du noyau, correct ; `builder.py` résout déjà `is not None` pour les nouveaux rendus). AMOT ne devient donc pas
`vérifié` tant que AMOT77 n'est pas construit et re-vérifié.

## 5. Optionnel (non déposé)

- AMOT35 : un vérificateur signale un jumeau (leçon 6) sans que le comportement diverge — jugé ok, non déposé.
- `builder.py::build_quote_data` garde volontairement un repli falsy `if devis.taux_tva else` pour les devis DÉJÀ ENVOYÉS
  (devis-envoyes-nouveaux-rendus.md) : ce N'EST PAS un écart (comportement scopé par le fondateur) — rappelé dans AMOT77.

## 6. Couverture et non-couvert

- **Couvert.** 31 tâches sur 66 cochées (toutes les P0/S1 + 25 %). Commits, tests nommés, code du moteur, règle #4.
- **Non couvert.** Les 35 autres tâches cochées ; aucun aller-retour en direct (lecture seule, sans pile) — la preuve live
  du groupe est AMOT51 (acceptation).
- **Statut du registre.** Après ce dépôt : 66/75 cochées (88 %), contre-visite mi-parcours avec **1 écart S2 + 1 écart S3**
  déposés en tâches (0 écart S1). La clôture (≥ 95 %) et la sortie du cycle restent dues ; AMOT ne sera `vérifié` qu'après
  construction + re-vérification d'AMOT77.

## 7. Coût

- 31 vérificateurs opus (effort élevé) : **≈ 2,61 M de jetons**, 586 appels d'outil, ≈ 41 min. Aucun appel Fable.
- Orchestrateur : échantillon déterministe, triage des 31 verdicts, vérification du site `generate_devis_premium.py:4834`
  et du dict `A_CORRIGER`, rédaction.

<!-- verifie | groupe: AMOT | pct: 88 | ecarts_s1_s2: 1 -->
