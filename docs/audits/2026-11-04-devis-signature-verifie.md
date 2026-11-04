# Vérifie ADVS — contre-visite de mi-parcours du parcours PA3 « devis → signature », 04/11/2026
<!-- verifie | groupe: ADVS | pct: 77 | ecarts_s1_s2: 1 -->

Commande `vérifie ADVS` (dû, mi-parcours : 34/44 cochées). Pour chaque tâche tirée : texte ↔ commits ↔ test nommé ↔ code de `main`, les 7 leçons de
`docs/claude-memory/lecons-construction-qjr5.md`, sondes rejouées. Rien construit, aucun deploy, aucun test Django local, rien lu ni écrit en production.
Écarts : ADVS45 (`docs/plans/PLAN_AUDIT_DEVIS.md`), ADVS46 (`docs/plans/PLAN_AUDIT_GENERATEUR.md`).

## 0. Préconditions

- **SHA.** `origin/main` = `06ced8b1a`. Pile : conteneur dédié monté sur ce code, base locale partagée `erp_db`, transaction annulée à chaque sonde.
- **Registre.** PA3 `devis-signature`, groupe ADVS, dossier `docs/audits/2026-11-02-parcours-PA3.md`.
- **Échantillon (graine = SHA + groupe) : 14 tâches.** P0/S1 (8) : ADVS1, 2, 4, 5, 6, 8, 25, 26 · 25 % du reste (6 sur 26) : ADVS11, 17, 19, 21, 32, 44.
- **Écart de méthode.** Vérificateurs sonnet / effort élevé au lieu d'opus (consigne de ce run) ; l'écart S2 est rejoué à part par l'orchestrateur (opus). Aucun appel Fable : aucun écart S1.

## 1. Vérificateurs (3 lots, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **14** | ADVS1, 2, 4, 5, 6, 8, 11, 17, 19, 21, 25, 26, 32, 44 |
| partiel / non-fait / faux / régression / déjà-présent | **0** | — |

ADVS1, ADVS2 et ADVS5 tiennent leur texte, mais la décision D-ADVS-1 nomme aussi la page publique : ADVS1 et ADVS2 la renvoyaient à une « tâche à numéroter », jamais déposée (§4).

## 2. Tests nommés

Tous présents, sur le comportement. Faibles : ADVS11 (ne regarde que `read_only` du sérialiseur ; C-ADVS-005 couvre le PATCH réel). Aucun test rejoué en local : lecture seule.

## 3. Sondes

Rejeu complet des 33 sondes du dossier : 32 `repro: false`, 1 REPRO : `C-ADVS-040-L2`, faux positif de la sonde (compare `'25400.0'` à `'25400.00'` en texte ; paniers divergents vides, TTC égaux). 5 rejeux affichent « base inchangée : non » : écritures concurrentes d'une autre lane sur `erp_db`. Sondes neuves :

| Sonde | Tâche | Résultat |
|---|---|---|
| `C-ADVS-VER1-101` | ADVS1, 2 | **REPRO** : `/proposal` 0 clé changée ; page publique 15 clés (`monthly_consumption.*` 838 → 465, `courbes_journalieres.consommation.hiver.kwh_jour` 28,0 → 15,5) |
| `C-ADVS-VER1-102` | ADVS4 | conforme : 3 signatures, 1 active, 2 archives, 3 clés d'exemplaire, octets de la 1re inchangés |
| `C-ADVS-VER1-201` | ADVS25 | conforme : même valeur sans faux positif, HMT et distance changent l'empreinte, ancienne empreinte 409 |
| `C-ADVS-VER1-202` | ADVS8 | conforme : sceau intact après renommage |
| `C-ADVS-VER1-301` | ADVS19 | conforme |
| `C-ADVS-VER1-302` | ADVS32 | conforme |
| `C-ADVS-VER1-303` | ADVS21 | conforme |
| `C-ADVS-VER1-304` | ADVS44 | conforme |

Exécuté sous node : `appartientAuPanierSans({designation:'Dyness BX51100', role_devis:'batterie'})` rend `true` (ADVS46).

## 4. Écarts déposés (`### ADVS — ÉCARTS vérifie 2026-11-04 · format v3`)

| Tâche | Sév. | Origine | Écart |
|---|---|---|---|
| ADVS45 | **S2** | ADVS1, 2 (D-ADVS-1) | la page publique d'un envoyé relit les tranches et la redevance du jour pour sa consommation : chiffre client qui bouge après envoi |
| ADVS46 | S3 | ADVS5 | le miroir écran des paniers ignore `role_devis` : une batterie à désignation libre sans produit lié reste dans le total « Sans » de l'écran (PDF et acompte justes) |

## 5. Optionnel (non déposé)

- `C-ADVS-040-L2` à corriger (comparer en `Decimal`). ADVS25 : docstring « Hors C&I : l'empreinte d'avant » vieillie.
- ADVS26 : le chemin de dédup ressert un brouillon d'avant la garde sans la rejouer. `_create_esign_record` reste best-effort à l'archivage (hypothétique).

## 6. Couverture et sortie de cycle

- **Couvert.** 14 tâches sur 34 cochées ; 33 + 8 sondes jouées.
- **Non couvert.** Les 20 autres cochées ; aucun rejeu navigateur ; aucun test exécuté. ADVS44 renvoie à ADVS43 PA3-01, dont l'étape ne la cite pas : sa sonde est sa seule exécution observée ici.
- **Cases vides avec commit.** ADVS3, 14, 22, 23, 24, 27, 36, 40, 41 ont un commit sur `main` et une case `[ ]` : non vérifiées ici, à reprendre à la clôture. Ancre en rapport : ADVS40 cite `apps/installations/selectors.py::blocage_annulation_acceptation`, introuvable (`check_ancres_taches.py`, non bloquant).
- **Statut.** 1 écart S2 : ADVS n'est pas `vérifié`. Clôture due à ≥ 95 %.

<!-- verifie | groupe: ADVS | pct: 77 | ecarts_s1_s2: 1 -->
