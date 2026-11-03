# Vérifie ALEA — 3ᵉ contre-visite de clôture du groupe lead (J1a), 03/11/2026
<!-- verifie | groupe: ALEA | pct: 100 | ecarts_s1_s2: 0 -->

Commande `loop audit` → `vérifie` dû (ALEA 100 % cochées, clôture : les écarts ALEA56-60 du 02/11 sont cochés). Deuxième
contre-visite consécutive à zéro S1-S2 après celle du 02/11 (`docs/audits/2026-11-02-lead-verifie.md`) : **le groupe sort du
cycle** (METHODE §C.4.3). Pour chaque tâche tirée : texte ↔ commits ↔ test nommé ↔ code de `main`, les 7 leçons de
`docs/claude-memory/lecons-construction-qjr5.md`, sondes rejouées. Les écarts confirmés deviennent des tâches v3 chez le
propriétaire des fichiers (ALEA61-65 `docs/plans/PLAN_AUDIT_LEAD.md`, ALEA66 `docs/plans/PLAN_AUDIT_DEPLOY.md`).

La contre-visite n'a rien construit, n'a lancé aucun deploy, aucun test local, et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `9ad3b8eb3`. Branche `verifie-alea-cloture-3`. Pile : conteneur `audit-pa1-django` sur ce worktree
  (code = `main`, 0 migration en attente).
- **Registre.** J1a `lead`, groupe ALEA, dossier `docs/audits/2026-10-07-lead.md` ; 54 tâches `[x]` lues dans les plans
  (LEAD, TRANSVERSE, DEPLOY, CALEPINAGE, GENERATEUR ; 56/56 au registre avec le ledger).
- **Échantillon (graine = SHA `9ad3b8eb3`) : 19 tâches.** P0/S1 : ALEA47, ALEA50 · écarts du 02/11 : ALEA56-60 · 25 % du
  reste (12 sur 47) : ALEA2, 6, 8, 11, 12, 19, 21, 24, 25, 28, 38, 52.
- **Déjà déposé, non redéposé.** L'audit de parcours PA1 (`docs/audits/2026-11-03-parcours-PA1.md`, PR #1248) couvre déjà :
  double cadence du doublon réveillé (ACVI16), gel des pièces d'une visite terminée (ACVI58), compensation du `DELETE` de
  visite (ACVI60), bouton « Renvoyer » sur une visite validée (ACVI67), « en retard » calendaire de l'écran Suivi (ACVI72),
  cause du 409 à l'écran (ACVI93).

## 1. Vérificateurs (3 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **15** | ALEA2, 6, 8, 11, 12, 19, 24, 25, 28, 38, 47, 52, 56, 58, 59 |
| partiel | **4** | ALEA21 (S3), ALEA50 (S3, sonde), ALEA57 (S3), ALEA60 (S3, sonde) |
| non-fait / faux / régression / déjà-présent | **0** | — |

Écart voisin hors texte : ALEA2 (réveil d'un Froid sans sortie de parcage, S3, sonde). Les écarts du 02/11 sont fermés :
ALEA56 (sonde VER2-001 `repro: false`), ALEA57 (jumeau non traité → ALEA64), ALEA58 (sonde VER2-101 `repro: false`, 7 tests
dont le refus d'une visite validée, nouveau et conforme), ALEA59 (ok), ALEA60 (garde branchée mais trouée → ALEA65/66).
Textes vieillis sans écart : refus en 409 (ENF11) là où les tâches disaient 400 (ALEA6, ALEA11).

## 2. Tests nommés

Tous présents ; ALEA21 en `.test.js` (vitest n'inclut pas `.mjs`, justifié). Tests faibles : ALEA2 `test_rejeu_idempotent`
(même clé : prouve la dédup d'événement, pas l'idempotence métier — la sonde couvre), ALEA60 épinglé sur une paraphrase
de la forme d'avant. Aucun test rejoué en local ; dernier run complet vert = d5fabd3c5 (#1244), sans changement de code depuis.

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ALEA/C-ALEA-VER2-001.py` | ALEA56 | ne reproduit plus (`_du_role` seule définition) |
| `docs/audits/sondes/ALEA/C-ALEA-VER2-002.py` | ALEA47 | non-régression (`profil_charge_prerequis_ci` partagée) |
| `docs/audits/sondes/ALEA/C-ALEA-VER2-101.py` | ALEA58 | ne reproduit plus (DELETE 204, visite, média et pièce du lead effacés) |
| `docs/audits/sondes/ALEA/C-ALEA-VER3-11.py` (neuve) | ALEA2 | non-régression d'ALEA2 (4/4) ; **REPRO** voisin : Froid `nurture/budget` réveillé passe NEW mais garde ses `parc_*` |
| `docs/audits/sondes/ALEA/C-ALEA-VER3-21.py` (neuve) | ALEA50 | **REPRO** : détail `catalogue_ci.pret=False` (12 postes) ; liste et PATCH `pret=True, catalogue_ci=None` |
| `docs/audits/sondes/ALEA/C-ALEA-VER3-31.py` (neuve) | ALEA59/60 | **REPRO** : `relance_date` un vendredi, lu le dimanche : résumé False, `relances?scope=overdue` et « Ma file » True |

Toutes en transaction annulée, base inchangée, 0 mail, une à la fois.

## 4. Écarts déposés (S3, `### ALEA — ÉCARTS vérifie 2026-11-03 · format v3`)

| Tâche | Origine | Écart |
|---|---|---|
| ALEA61 | ALEA2 | `reactivate_lead_on_new_touch` ne vide pas `parc_etat`/`parc_raison` : le lead réveillé reste « Nurture » et `_reveiller_lead_parque` arrête sa reprise |
| ALEA62 | ALEA21 | `fetchLeads.rejected` éteint `fetchLeadsInFlight` sans garde `requestId` : un fetch annulé (filtre Archivés) laisse écraser une étape déplacée |
| ALEA63 | ALEA50 | `catalogue_ci` calculé au seul GET détail : liste et PATCH servent `pret=True` pour un catalogue non prêt (boutons et ⌘K actifs) |
| ALEA64 | ALEA57 | `VisiteMesuresForm` muet sur `erreurs.statut` / `corps` / `categorie` (jumeau non traité) |
| ALEA65 | ALEA59/60 | `relances_du_jour` filtre `relance_date__lt` en jours calendaires : deux définitions du retard sur le même champ |
| ALEA66 | ALEA60 | la garde `check_retard_unique.py` ignore `relance_date__lt=` et les alias de clé ; test épinglé sur une paraphrase |

Optionnel, sans tâche : ALEA25 docstring périmé (Commercial canonique en `SCOPE_SELF` depuis le 26/10) ; ALEA21 (b)
`fetchClients.fulfilled` remplace tout le tableau sans mention au commit ; ALEA19 `entite` suivi mais non testé.

## 5. Dette d'acceptation

Preuves en direct couvertes pour ALEA6, 8, 12, 19, 47, 52, 56, 57, 58 (enregistrements P1.3, P3.x, 676f4f49c,
369cf21d8) ; non couvertes (dette gelée) : ALEA2, 11, 21, 28, 38. `check_acceptation.py --groupe ALEA` : 20 non couvertes.

## 6. Limites

- Aucun test unitaire ni vitest rejoué ; ALEA21 et ALEA57 établis par lecture (S3) ; écrans non rejoués en navigateur.
- Sondes citées par les tâches v2 (`scratchpad` LVIS, LCOUT, LFICHE) absentes du dépôt ; `freezegun` absent du conteneur
  (la sonde VER3-31 passe le jour aux fonctions, pas aux routes).
- Sortie du cycle acquise (10/10 et 02/11 à zéro S1-S2, 03/11 à zéro) ; les S3 restent à construire.

## 7. Coût

3 vérificateurs opus / high + 1 rédacteur opus ≈ 1,0 M jetons de sous-agents ; 3 sondes neuves, 3 rejouées.
