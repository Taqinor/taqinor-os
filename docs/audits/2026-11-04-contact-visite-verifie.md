# Vérifie ACVI — contre-visite de mi-parcours du parcours PA1 « contact → visite », 04/11/2026
<!-- verifie | groupe: ACVI | pct: 63 | ecarts_s1_s2: 1 -->

Commande `vérifie ACVI` (dû, mi-parcours : 62/98 cochées). Pour chaque tâche tirée : texte ↔ commits ↔ test nommé ↔ code de `main`, les 7 leçons de
`docs/claude-memory/lecons-construction-qjr5.md`, sondes rejouées. Rien construit, aucun deploy, aucun test Django local, rien lu ni écrit en production.
Écarts : ACVI100 (`docs/plans/PLAN_AUDIT_LEAD.md`), ACVI101 (`docs/plans/PLAN_AUDIT_ACQUISITION.md`).

## 0. Préconditions

- **SHA.** `origin/main` = `06ced8b1a`. Pile : conteneur dédié monté sur ce code, base locale partagée `erp_db`, transaction annulée à chaque sonde.
- **Registre.** PA1 `contact-visite`, groupe ACVI, dossier `docs/audits/2026-11-03-parcours-PA1.md`.
- **Échantillon (graine = SHA + groupe) : 18 tâches.** P0/S1 (4) : ACVI1, 21, 44, 90 · 25 % du reste (14 sur 58) : ACVI14, 17, 18, 20, 27, 34, 60, 64, 66, 67, 71, 79, 82, 99.
- **Écart de méthode.** Vérificateurs sonnet / effort élevé au lieu d'opus (consigne de ce run) ; l'écart S2 est rejoué à part par l'orchestrateur (opus). Aucun appel Fable : aucun écart S1.

## 1. Vérificateurs (3 lots, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **17** | ACVI1, 14, 17, 18, 20, 21, 27, 34, 44, 60, 66, 67, 71, 79, 82, 90, 99 |
| régression | **1** | ACVI64 (S3, clause tenue, effet de bord : la texture de toit) |
| partiel / non-fait / faux / déjà-présent | **0** | — |

Textes vieillis sans écart : ACVI27 (« 2 touches », 1 aujourd'hui, prochain geste CKP2) ; ACVI71 (commercial d'une autre société : 404, pas le 400 du texte, sans écriture).

## 2. Tests nommés

Tous présents, sur le comportement ; ACVI67 sous un autre nom que celui du plan. Seul test exécuté : `scripts/tests/test_check_garde_contact.py` (7 verts, ACVI90). Tests Django et vitest non rejoués : lecture seule.

## 3. Sondes

Rejeu complet des 85 sondes du dossier : 16 fichiers REPRO, 69 `repro: false`. Chaque REPRO a été lu, sous-défaut par sous-défaut :

| Sonde (composite) | Sous-défaut encore vrai | Lecture |
|---|---|---|
| C-ACVI-140+141 | mot `etude_params` dans le SQL | faux positif pour ACVI77/78 (chemins JSON annotés, permis) ; **vrai sur l'attribution** → ACVI101 |
| C-ACVI-143+144+147 | H5, 41 requêtes à 12 leads | artefact : 8 leads écrits à ce passage, la clause d'ACVI81 porte sur « sans écriture » |
| C-ACVI-025+033 | `B14_sans_chatter` | le refus est journalisé en `records.Activity`, la sonde lit `LeadActivity` : artefact (ACVI91, ACVI99) |
| C-ACVI-002+008 | porte RDV sans owner ni touche | contrat YBW51 ; ACVI88 traite le reste |
| C-ACVI-001+004+009 | A9, `+212…` stocké | sans tâche au dossier ; `phone_normalise` juste |
| C-ACVI-024+…+040 | `B21`, perdu sans motif | sans tâche au dossier (cité en voisin) |
| C-ACVI-149+153 | H14, 429 au 6e appel formulaire éteint | sans tâche au dossier ; H10 (ACVI84) tenu |

La composite `C-ACVI-169+170+175+174+173` plante sur un corps d'activité `None` (sonde à corriger) : ACVI61, 62, 65 n'ont donc pas été rejouées par elle, ACVI64 l'est par VER1-201. 33 rejeux affichent « base inchangée : non » : écritures concurrentes sur `erp_db`, non attribuées une à une ; recherche de résidus par nom des sondes VER1 : 0 lead, 0 utilisateur, 0 société. Sondes neuves :

| Sonde | Tâche | Résultat |
|---|---|---|
| `C-ACVI-VER1-101` | ACVI21 | conforme |
| `C-ACVI-VER1-102` | ACVI44 | conforme |
| `C-ACVI-VER1-103` | ACVI14 | conforme |
| `C-ACVI-VER1-104` | ACVI17 | conforme |
| `C-ACVI-VER1-106` | ACVI77, 78, 94 | les 4 sélecteurs d'ACVI78 : 0 JSON entier ; **REPRO** : `attribution_leads` et `revenu_attribue_campagne`, 2 requêtes |
| `C-ACVI-VER1-201` | ACVI64 | conforme (feu vert) |
| `C-ACVI-VER1-202` | ACVI64 | **REPRO** : V2 validée sans photo retire la texture de V1 |
| `C-ACVI-VER1-203` | ACVI18, 27, 34, 60 | conforme |
| `C-ACVI-VER1-301` | ACVI66 | conforme |
| `C-ACVI-VER1-302` | ACVI71 | conforme |
| `C-ACVI-VER1-303` | ACVI79 | conforme (48 puis 47 requêtes à 3 et 9 leads, ~5 par jour distinct) |
| `C-ACVI-VER1-304` | ACVI82 | conforme |
| `C-ACVI-VER1-305` | ACVI99 | conforme |

## 4. Écarts déposés (`### ACVI — ÉCARTS vérifie 2026-11-04 · format v3`)

| Tâche | Sév. | Origine | Écart |
|---|---|---|---|
| ACVI101 | **S2** | ACVI78 | l'attribution décode encore le JSON d'étude (jusqu'à 1,45 Mio par devis) : ACVI78 la renvoyait à une tâche « à numéroter », jamais déposée |
| ACVI100 | S3 | ACVI64 | une V2 validée sans photo retire la texture de V1 (filtre retiré au commit 130806b40, docstring non réaligné) |

## 5. Optionnel (non déposé)

- `cadence_messages.py::_nom_affiche_conseiller` lit `responsable_defaut_leads` sans `is_active` ; `dispatch.py::marquer_en_attente` rend `equipe.responsable` sans contrôle (non sondé).
- `check_garde_contact.py::_a_un_message` ne lit que le 2e positionnel. ACVI66 : migration 0009 ne reprend pas les anciennes annulations. ACVI99 : un refus de plus à chaque import. Liste blanche « A CORRIGER (ACVI89/ACVI98) » vieillie.

## 6. Couverture et sortie de cycle

- **Couvert.** 18 tâches sur 62 cochées ; 85 + 13 sondes jouées ; sélecteurs d'ACVI78 mesurés hors échantillon par le rejeu.
- **Non couvert.** Les 44 autres cochées ; aucun rejeu navigateur ; ACVI67 lu seulement (ni vitest ni navigateur ici).
- **Cases vides avec commit.** ACVI2, 3, 6, 8, 10, 11, 13, 24, 31, 36-43, 46, 51-54, 57, 63, 72-76, 88, 89, 94, 95, 97, 98 ont un commit sur `main` et une case `[ ]` : non vérifiées ici, à reprendre à la clôture.
- **Statut.** 1 écart S2 : ACVI n'est pas `vérifié`. Clôture due à ≥ 95 %.

<!-- verifie | groupe: ACVI | pct: 63 | ecarts_s1_s2: 1 -->
