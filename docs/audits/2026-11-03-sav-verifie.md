# Vérifie ASAV — 3ᵉ contre-visite de clôture du groupe sav (J4), 03/11/2026
<!-- verifie | groupe: ASAV | pct: 100 | ecarts_s1_s2: 0 -->

Commande `loop audit` → `vérifie` dû (108/108 cochées, clôture). La contre-visite du 01/11 (`docs/audits/2026-11-01-sav-verifie.md`)
avait déposé ASAV115-122, dont un S1 (ASAV5, quotas du contrat, refermé par ASAV122). Toutes sont cochées. Pour chaque tâche
tirée : texte ↔ commits ↔ test nommé ↔ code de `main`, les 7 leçons de `docs/claude-memory/lecons-construction-qjr5.md`, sondes
rejouées. Les écarts confirmés deviennent des tâches v3 chez le propriétaire des fichiers (ASAV123-128, `docs/plans/PLAN_AUDIT_SAV.md`).

La contre-visite n'a rien construit, n'a lancé aucun deploy, aucun test local, et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `9ad3b8eb3` (PR #1248 mergée). Branche `verifie-asav-cloture-2`. Pile : conteneur `audit-pa1-django` sur
  ce worktree (code = `main`, base clonée de la démo, 0 migration en attente).
- **Registre.** J4 `sav`, groupe ASAV, dossier `docs/audits/2026-10-08-sav.md` ; 109 tâches, 108 `[x]`, ASAV72 `[BLOCKED: sans objet]`.
- **Échantillon (graine = SHA `9ad3b8eb3`) : 39 tâches.**
  - Les P0/S1 cochées : ASAV2, 3, 4, 5, 6, 7, 99, 105 (ASAV122 déjà parmi les écarts).
  - Les 8 écarts du 01/11 : ASAV115 à 122.
  - 25 % du reste (23 sur 92) : ASAV9, 15, 20, 21, 26, 27, 35, 41, 46, 52, 53, 55, 59, 60, 75, 90, 92, 93, 100, 102, 109, 111.
- **Déjà déposé, non redéposé.** AARG (PA4) et ACVI (PA1) sur les coutures sav ↔ lead (ACVI12/88 : ticket SAV → lead).

## 1. Vérificateurs (5 lots de 7-8, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **32** | ASAV2, 3, 4, 5, 6, 7, 15, 21, 26, 27, 35, 41, 46, 52, 53, 60, 90, 92, 93, 94, 100, 102, 105, 109, 111, 115, 116, 117, 118, 119, 120, 122 |
| partiel | **7** | ASAV9 (S3), ASAV20 (S3, sonde), ASAV55 (S3), ASAV59 (S3), ASAV75 (S3), ASAV99 (S3, acceptation), ASAV121 (S3, acceptation) |
| non-fait / faux / régression / déjà-présent | **0** | — |

ASAV5, « partiel S1 » le 01/11, est refermé : `droits_contrat.py::lignes_consommatrices` est partagée par la fiche et la liste,
sondes `C-ASAV-VER2-31` et `C-ASAV-VER3-11` (Given complet rejoué par HTTP, trois jeux) → `repro: false`. Les sondes des écarts
du 24/10 et du 01/11 (`C-ASAV-VER-002`, `C-ASAV-VER2-411`, `C-ASAV-VER2-71`) ne reproduisent plus.

## 2. Tests nommés

Tous présents. Renommages voulus : ASAV9 `_400` → `_409` (ENF11), ASAV6 `test_sans_chantier_reste_none` remplacé (chantier
toujours créé à l'acceptation, jugé voulu le 24/10). Tests faibles relevés : ASAV21 (persistance par `.update()`), ASAV41 et
ASAV53 (clause « rouvrir » / « panneau non modifié » non vérifiée à l'écran), ASAV55 (faux serveur qui fabrique `SAV-00${ticket}`
et masque l'écart), ASAV59 (ni pièces jointes ni historique), ASAV75 (garde plus étroite que son contrat), ASAV116 (mutant
indiscernable, servi par le serveur). Aucun test rejoué en local (CI d'abord ; CI verte de #1217 pour ASAV116-122).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ASAV/C-ASAV-VER2-31.py` | ASAV5 / ASAV122 | ne reproduit plus (`repro: false`, facturer 201, ligne 0,00, 2 déplacements consommés) |
| `docs/audits/sondes/ASAV/C-ASAV-VER3-11.py` (neuve) | ASAV5 | Given complet par HTTP, 3 jeux : couverture fiche = liste, factures 0,00 / 5 000,00, consommés exacts ; `ecarts=[]` |
| `docs/audits/sondes/ASAV/C-ASAV-VER-002.py` | ASAV105 | ne reproduit plus (facturable, 5 000,00) |
| `docs/audits/sondes/ASAV/C-ASAV-VER2-411.py` | ASAV115 | ne reproduit plus (`sla_breach=True`, notification émise ; compteur de la sonde mal calibré, le test filtre bien) |
| `docs/audits/sondes/ASAV/C-ASAV-VER2-71.py` | ASAV117 | ne reproduit plus (« À confirmer (garantie de chantier) », facturer 409) |
| `docs/audits/sondes/ASAV/C-ASAV-VER3-21.py` (neuve) | ASAV20 | **REPRO** : ticket en retard sans technicien → scan 15 min pose `sla_breach` sans notifier, balayage quotidien ne le voit plus : 0 notification (avec technicien : 1) |

Toutes en transaction annulée, base inchangée, 0 mail, 0 tâche Celery, une à la fois.

## 4. Écarts déposés (S3, `### ASAV — ÉCARTS vérifie 2026-11-03 · format v3`)

| Tâche | Origine | Écart |
|---|---|---|
| ASAV123 | ASAV9 | la résolution « remplacement » d'une réclamation fournisseur n'appelle pas `remplacer_equipement` (aucun neuf au parc ni au contrat) ; `piece_retiree.json` reste « partielle » |
| ASAV124 | ASAV20 | course scan / balayage sur la clé `sla_breach` : un ticket en retard sans technicien n'alerte personne |
| ASAV125 | ASAV55 | « N° du ticket à lier » envoyé comme pk, l'écran ne montre que la référence |
| ASAV126 | ASAV59 | après fusion, les pièces jointes du doublon ne s'affichent qu'au rechargement de la page |
| ASAV127 | ASAV75 | la garde `statut` ne voit que les variables nommées « ticket » (1 écriture sur 5 signalée) |
| ASAV128 | ASAV99, ASAV121 | acceptation : P99.5 jamais jouée, sous-clauses (2), (4), (7), (8) non vérifiées, DONE LOG inexact (ASAV99 « 18/18 », ASAV114 cite l'enregistrement FAIL), captures vides |

Optionnel, sans tâche : ASAV90/92/93/94 consignées dans `decisions-audit-0810.md` et non dans le fichier
`sav-decisions-fondateur.md` demandé (S4) ; ASAV41 réservé par rôle et non par `prix_achat_voir` (S4) ; ASAV46 puce d'échéance
encore calendaire (S4) ; ASAV111 verdict `a_determiner` à date passée affiché « Garantie jusqu'au » (S4) ; ASAV116 mutant
indiscernable ; ASAV120 mutant « en-tête inchangé » non tué ; ASAV4 mention « garantie légale » du PDF jugée au jour d'impression.

## 5. Dette d'acceptation

`check_acceptation.py --groupe ASAV` : 90 cochées à preuve, 16 couvertes, 74 non couvertes (dette gelée = non couvertes,
0 divergence). Dans l'échantillon, seules ASAV105, 109, 111, 115 (P114.x), 116-119, 121, 122 sont couvertes ; les P0/S1
ASAV2-7 et ASAV9, 53, 55, 59, 60, 100, 102 sont en dette. ASAV100-103 à preuve et en dette.

## 6. Limites

- Verdicts par lecture du code et des tests pour les tâches sans sonde ; aucun test unitaire ni vitest rejoué.
- Sondes citées par les tâches v2 (`scratchpad/j4/…`, STIK, SPUB, SEVT, SUI) absentes du dépôt : non rejouables.
- Aucun rendu PDF ni passage à l'écran ; Playwright non rejoué (preuves jugées sur enregistrements et captures).
- Sortie du cycle : la contre-visite du 01/11 portait un S1 ; celle-ci est à zéro S1-S2. Une prochaine à zéro signera la sortie.

## 7. Coût

5 vérificateurs opus / high + 1 rédacteur opus ≈ 1,3 M jetons de sous-agents ; 2 sondes neuves, 5 rejouées.
