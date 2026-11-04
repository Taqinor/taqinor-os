# Vérifie AARG — contre-visite de mi-parcours du parcours PA4 « argent », 04/11/2026
<!-- verifie | groupe: AARG | pct: 82 | ecarts_s1_s2: 1 -->

Commande `vérifie AARG` (dû, mi-parcours : 48/58 cochées). Pour chaque tâche tirée : texte ↔ commits ↔ test nommé ↔ code de `main`,
les 7 leçons de `docs/claude-memory/lecons-construction-qjr5.md`, sondes rejouées. La contre-visite n'a rien construit, n'a lancé
aucun deploy ni aucun test Django local, et n'a rien lu ni écrit en production. Les écarts deviennent des tâches v3 chez le
propriétaire (AARG59-62, `docs/plans/PLAN_AUDIT_FACTURATION.md`).

## 0. Préconditions

- **SHA.** `origin/main` = `06ced8b1a`. Pile : conteneur dédié monté sur le code de `06ced8b1a`, base locale partagée `erp_db` (migrations
  identiques), transaction annulée à chaque sonde. La pile de rejeu voisine n'a été ni redémarrée ni reconstruite.
- **Registre.** PA4 `argent`, groupe AARG, dossier `docs/audits/2026-11-02-parcours-PA4.md`.
- **Échantillon (graine = SHA + groupe) : 18 tâches.** P0/S1 (8) : AARG1, 2, 4, 7, 8, 11, 28, 52 · 25 % du reste (10 sur 40) : AARG3, 14, 18, 22, 30, 31, 32, 36, 56, 58.
- **Écart de méthode.** Vérificateurs sonnet / effort élevé au lieu d'opus (consigne de ce run) ; les écarts S1-S2 sont rejoués à part par
  l'orchestrateur de la contre-visite (opus). Aucun appel Fable : aucun écart S1.

## 1. Vérificateurs (3 lots, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **17** | AARG1, 2, 3, 4, 7, 8, 11, 14, 18, 28, 30, 31, 32, 36, 52, 56, 58 |
| partiel | **1** | AARG22 (S3, leçon 2 : l'exclusion tient, la reprise automatique après levée non) |
| non-fait / faux / régression / déjà-présent | **0** | — |

AARG1, AARG56 et AARG58 tiennent leur texte ; chacune a un écart voisin hors texte (§4). Texte vieilli sans écart : AARG22 écrit 400, le code
et le test font 409 (ENF11) ; AARG58 écrit « comme la relance manuelle » alors que la manuelle n'attache rien.

## 2. Tests nommés

Tous présents, sur le comportement. Faibles : AARG7 (témoin Directeur `!= 403`), AARG11 (ni PATCH 403 ni 201 Directeur, couverts par la sonde 106),
AARG32 (branches Commercial refusées par `IsResponsableOrAdmin`, le filtre `peut_passer_outre` peut sauter sans rougir), AARG22 (pas la reprise).
**Aucun test rejoué en local** (CI d'abord) : lecture seule.

## 3. Sondes

Rejeu complet des 32 sondes du dossier sur `06ced8b1a`, une à une : 32 `repro: false`. `C-AARG-021` s'arrête sur `FusionRefusee` (la fusion refuse désormais
le cas, ce qui est le correctif : pas d'écart) ; `C-AARG-018` ne vaut plus preuve (elle teste l'absence du champ). 9 rejeux affichent « base inchangée : non » : écritures
concurrentes d'une autre lane sur `erp_db` ; une sonde jouée à part (VER1-107) ressort inchangée. Sondes neuves :

| Sonde | Tâche | Résultat |
|---|---|---|
| `C-AARG-VER1-101` | AARG1 | conforme ; D observé : annuler l'avoir laisse dû 2 400 et avance 2 400 libre |
| `C-AARG-VER1-102` | AARG2 | conforme (nominal, 409 si avance utilisée, part gardée) |
| `C-AARG-VER1-103` | AARG4 | conforme (base RAS nette des avoirs et notes de débit) |
| `C-AARG-VER1-104` | AARG7 | conforme ; `annuler` + `garder_en_avance` passe sans `encaisser` (§5) |
| `C-AARG-VER1-105` | AARG8 | conforme |
| `C-AARG-VER1-106` | AARG11 | conforme |
| `C-AARG-VER1-107` | AARG1 | **REPRO** : statut emise, dû 2 400, avance 2 400 libre, `facture_relancable` vrai |
| `C-AARG-VER1-201` | AARG22 | exclusion tenue ; `ecart_reprise_beat_apres_levee: true` |
| `C-AARG-VER1-202` | AARG52 | conforme (1 296 gardes inventoriées, aucun module non résolu hors fondation) |
| `C-AARG-VER1-301` | AARG30 | conforme |
| `C-AARG-VER1-302` | AARG31, 32 | conforme |
| `C-AARG-VER1-303` | AARG36 | conforme (PDF réel relu : bases par taux) |
| `C-AARG-VER1-304` | AARG58 | conforme ; relance manuelle sans pièce jointe observée |
| `C-AARG-VER1-305` | AARG56 | conforme ; `divergence_delai_client: true` |

## 4. Écarts déposés (`### AARG — ÉCARTS vérifie 2026-11-04 · format v3`)

| Tâche | Sév. | Origine | Écart |
|---|---|---|---|
| AARG59 | **S2** | AARG1 | annuler un avoir ordinaire rouvre la facture et laisse l'avance libre : relance possible d'une somme déjà versée |
| AARG60 | S3 | AARG22 | le beat efface `prochaine_relance` d'une contestée : plus de relance automatique après la levée |
| AARG61 | S3 | AARG56 | recalcul à émission + 30 j, beat au délai négocié du client (lignes historiques sans date) |
| AARG62 | S3 | AARG58 | la relance manuelle par e-mail n'attache pas le PDF, l'automatique si |

## 5. Optionnel (non déposé)

- `solde_courant` du portail vaut `totaux.du` (0) alors que le compte a un crédit (`totaux.solde` −2 400 dans la même réponse) : aucun lecteur d'écran (grep front, apps/web : 0).
- `annuler` + `garder_en_avance` sans `encaisser` : Admin Ventes crée une avance libre, qu'il ne peut pas dépenser (`ventiler` gardé).
- AARG58 : au 3e échec de rendu PDF, la notification dit « adresse e-mail à corriger ». AARG3 : docstrings « statut payee » périmées. AARG52 : `FERMEES_EN_ECRITURE_ATTENDUES` périmée.
- AARG30 : `has_facture` vrai sur un BC dont la facture est annulée, lu par `BonCommandeList.jsx` et `documentChain.js`.

## 6. Couverture et sortie de cycle

- **Couvert.** 18 tâches sur 48 cochées ; 32 + 14 sondes jouées.
- **Non couvert.** Les 30 autres cochées ; aucun rejeu navigateur ; aucun test exécuté. AARG3, 4, 7, 11, 14, 18, 22, 31, 52 ne sont dans aucun `couvre:` (« API seulement », renvoi à AARG50, encore ouverte) : leurs sondes sont leur seule exécution observée ici ; `check_acceptation.py` est vert.
- **Cases vides avec commit.** AARG6, 10, 29, 33, 34, 35, 44, 46, 57 ont un commit sur `main` et une case `[ ]` : non vérifiées ici, à reprendre à la clôture.
- **Statut.** 1 écart S2 : AARG n'est pas `vérifié`. Clôture due à ≥ 95 %.

<!-- verifie | groupe: AARG | pct: 82 | ecarts_s1_s2: 1 -->
