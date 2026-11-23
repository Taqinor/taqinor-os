# C4 — Consolidation du chemin « un seul moteur » (23/11/2026)
Sortie : `C4-taches-v3.md` (55 tâches v3, une ligne chacune, groupées par plan) ; `C4-un-seul-moteur.md` §9 et §8 mis à jour
avec les quatre réponses du fondateur. Rien n'est écrit dans un plan, rien n'est commité.

**Comptes (plan → niveau).** DEVIS 27 (M0 2, M1 23, M2 1, GATED 1) · LEAD 4 (M1) · CALEPINAGE 19 (M0 1, M1 12, M2 3, acceptation 3)
· GENERATEUR 2 (M1) · DEPLOY 1 (M2) · TRANSVERSE 2 (M1 1, M2 1). Modèles : 24 opus, 29 sonnet, 2 haiku.
**Ids.** ADEV129-ADEV155 · ALEA68-ALEA71 · ACAL2010-ACAL2029 (20, dont 1 en transverse) · AGEN11-AGEN13 (dont AGEN13 en
transverse) · ADEP108. Les deux tâches transverses gardent le préfixe de leur groupe (ACAL2021, AGEN13).
| Étape | Tâches (id) |
|---|---|
| E1 contrat | ADEV129 (JSON), ACAL2010 (3 événements), ADEV130 (champs) |
| E2 moteur | ADEV131 modèle, 132 entrées, 133 moteur, 134 suppositions, 135 écrivain, 136 porteur calepinage (Q3), 137 sélecteurs + route, 138 PARITÉ |
| E3 relance | ALEA68 émission lead, ACAL2011 émission pose, ADEV139 tâche dédupliquée, 140 filet, ALEA69 chatter, ADEV141 remplissage |
| E4 devis | ADEV142 devis auto, 143 pointeur + études, 144 + 145 PARITÉ, ALEA70 garde CRM, ADEV146 écart devis, 147 + 148 + AGEN12 (Q2), ACAL2027 acceptation (E3 + E4) |
| E5 calepinage | ACAL2012 cible, 2013 matériel, 2014 longueur + constantes AO, 2015 Résultats, 2016 contrôles, 2017 PARITÉ, 2028 acceptation |
| E6 pose | ACAL2018 façade, ADEV149 appel, 150 pose souveraine, ACAL2019 bouton, 2020 consommation, ADEV151 PARITÉ + liste des écarts |
| E7 écrans | ALEA71 fiche, ACAL2021 pastille, ADEV152 aperçu, AGEN11 écran devis, ACAL2022 atelier (Q4), 2023 client, ADEV153 chiffrage, ACAL2029 acceptation (E6 + E7) |
| E8 retraits | AGEN13 maths locales, ACAL2024 second bilan, ACAL2025 lignes du devis, ADEP108 garde |
| E9 sans toit (Q1) | ACAL2026 simulation d'un toit supposé, ADEV154 liste des écarts, ADEV155 bascule (GATED, liste lue par le fondateur AVANT) |

**Tranché.** (1) 48 tâches de C4 → 55 : fusion de 9+10 et 19+20, 44 absorbée par 27 (même fichier, même règle), 31 et 38
scindées par propriétaire, 48 scindée en capacité (ACAL2026), liste (ADEV154), bascule (ADEV155, GATED : la liste ne peut pas dépendre
de ce qu'elle doit précéder), +Q2 (3 tâches), +Q3 (1), +3 acceptations. (2) La branche « production de la pose » du moteur ne s'ouvre qu'au
niveau de règles 15 (ACAL1001 reste GATED) : au 14 courant la parité de l'étape 2 reste intacte. (3) Les 3 événements sont réservés dans
`core/event_coverage.py::ALLOWED_UNCONSUMED` (sinon `test_event_coverage` rougit) ; ADEV139 et ALEA69 retirent leurs entrées. (4) « Retouché
à la main » = `Devis.overrides` non vide ou une ligne `quantite_manuelle` / `prix_manuel` (registre existant). (5) Le point de bascule de la cible
est `calepinage/services/devis.py::_cible_du_calepinage`, pas `toiture_lead.py`. (6) La saisie CSV / appareils du calepinage reste une entrée
IMPOSÉE du calepinage (pas de colonne `releve_conso` sur le lead : non vérifié) — écart avec C4 §7. (7) ACAL2010 est au plan calepinage (ses 5
fichiers sont des surfaces append-only) ; ACAL2021 (calepinage + devis) et AGEN13 (générateur + moteur : tests différentiels Python) vont au
transverse avec `@atomique`, la règle (d) n'y attend que des déplacements : à scinder si elle devient bloquante. (8) La parité des 104 goldens vit
dans `test_conception_lead.py` (le module des goldens appartient à `moteur`). (9) Les goldens `split_dm_auto*.json` sont dans `tests/golden/`, pas `golden/moteur/`.

**Vérifié (outil, cette session).** 0 id en double, 0 id déjà dans un plan ; 97 ancres `fichier::symbole` résolues ; chaque `Files:` existe ou est
« à créer » (« à créer par <id> » pour un fichier créé plus haut) ; chaque `@after` pointe un id du fichier ; `plan_lanes.py` : 0 refus, pas de cycle
(54 constructibles + 1 GATED) ; `check_taches_cablage` (formes 1, 3, 5, regex d'audit forcée) : 0 constat ; `check_ownership --owner-of` : chaque
tâche est chez le propriétaire de ses fichiers (hors les 2 transverses).
**Non vérifié.** Aucun test lancé ; `audit_tache.py`, `check_ancres_taches.py`, `check_decisions.py`, `audit_registre.py --check` non lancés (le
fichier n'est dans aucun plan) ; les clauses « Appelants » viennent de `git grep` du 23/11, pas d'`audit_tache.py` ; 33 lignes dépassent 3 500
caractères (max 4 648, cible 2 400) ; numéro de migration 0161 et ids ADEV129+ à relire si la vague D en pose d'autres ; la capacité d'un plan virtuel
dans `construire_contexte` (ACAL2026) reste « probable » ; `D-ACAL-97` n'enregistre pas encore les réponses Q1-Q4 (à écrire par l'orchestrateur).
