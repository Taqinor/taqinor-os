# Vérifie AFAC — 3ᵉ contre-visite de clôture du groupe facturation (J5), 02/11/2026

Commande `continue audit` → `audit next` → `vérifie AFAC`. Le groupe était déjà sorti du cycle le 11/10 (mi-parcours et
clôture à zéro S1-S2) ; cette contre-visite confirme la sortie sur le code du jour, après trois semaines de vagues qui ont
touché la facturation, et le jour même où l'audit de parcours PA4 a déposé AARG1-58 sur le même terrain.

La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en prod. Pile locale : migrations manquantes
(facturation 0024/0025, ventes 0148) appliquées avant de rejouer les sondes.

## 0. Préconditions

- **SHA.** `origin/main` = `1dfa7986c`. Branche de claim : `verifie-afac-2`.
- **Registre.** J5 `facturation`, groupe AFAC, 92 tâches, 89 `[x]` (AFAC35-37 BLOCKED sans objet, D-AFAC-83).
- **Échantillon (graine = SHA `1dfa7986c`).** Toutes les P0/S1 cochées (14) + 25 % du reste (18 sur 75) = **32 tâches**.
- **Déjà déposé, non redéposé.** Écarts voisins trouvés par l'audit de parcours PA4 (`docs/audits/2026-11-02-parcours-PA4.md`) :
  AARG6 (import hors J+7, écart d'AFAC9), AARG10 (pile carte FG370), AARG13 (portée du rôle), AARG22 (contestée),
  AARG24/25/58 (relance sans PDF ni montant, voisin d'AFAC42), AARG33, AARG35, AARG39.

## 1. Vérificateurs (4 lots de 8, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **29** | AFAC1, 3, 5, 10, 11, 12, 13, 14, 22, 26, 27, 32, 33, 40, 41, 42, 47, 51, 55, 59, 65, 66, 68, 70, 80, 81, 90, 94, 96 |
| déjà-présent (conforme) | **1** | AFAC64 (construit par ADEV35) |
| partiel | **2** | AFAC67 (S3, source mockée), AFAC99 (preuve en direct : oracle 10 jamais joué) |
| non-fait / faux / régression | **0** | — |

AFAC81, partiel à la clôture du 11/10, est désormais ok (en-tête gravé par AFAC102). AFAC27 : réserve de test levée par
sonde (remise 15 % + pas d'arrondi combinés).

## 2. Tests nommés

Tous présents ; deux tests déplacés dans un module existant du propriétaire (AFAC14 → `test_aud101_emission_unique.py`,
AFAC90 → `test_atot_portes_facturation.py`), légitime (règle « module de test existant »). Tests faibles relevés : AFAC65
(« après paiement » ne vérifie qu'un second GET), AFAC67 (forme de réponse inventée). Aucun test rejoué en local (CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/AFAC/C-AFAC-VER2-010.py` | AFAC27 | conforme : 2 retours partiels → avoirs 10 200 + 10 200 = TTC 20 400, dû 0 |
| `docs/audits/sondes/AFAC/C-AFAC-VER2-020.py` | AFAC67 | REPRO : `creer-facture` sert `montant_ttc: null`, `total_ttc: 12000.00` ; l'écran lit le premier |
| `docs/audits/sondes/AFAC/C-AFAC-VER2-030.py` | AFAC99 | oracle 10 joué : 0 violation sur les factures du flux J5 ; 2 violations sur la facture de seed FAC-DEMO-0002 |

## 4. Écarts retenus (S3 seulement)

| C-id | Tâche d'origine | Écart | Sonde | Tâche |
|---|---|---|---|---|
| C-AFAC-VER2-040 | AFAC13 | dialogue d'annulation : cibles « même client », le serveur exige même devis + encaissable + reste suffisant | STATIQUE | AFAC103 |
| C-AFAC-VER2-041 | AFAC5 | une saisie importée puis annulée bloque la ligne de relevé pour toujours (`doublon_import`) | STATIQUE | AFAC104 |
| C-AFAC-VER2-020 | AFAC67 | confirmation « Total TTC — » (champ de tranche lu au lieu de `total_ttc`) | REPRO | AFAC105 |
| C-AFAC-VER2-030 | AFAC99 | seed : FAC-DEMO-0002 « payée » sans paiement, échéance avant émission → oracle 10 rouge à vie | REPRO | AFAC106 |

Preuve d'AFAC99 complétée par C-AFAC-VER2-030 (oracle 10 vert sur le flux) ; le compte « 14/14 » du DONE LOG pour un
enregistrement de 13 étapes est une erreur d'écriture, pas de construction.

## 5. Optionnel (non déposé)

- AFAC14 : échéance future gardée à la réémission (conforme au texte ; voir aussi D-AARG-4 / AARG23).
- AFAC47 : `ParametrageRelanceClient.client` est un OneToOne global (une ligne corrompue bloquerait une autre société) — non mesuré.
- AFAC80 : la phrase du fondateur n'est pas recopiée dans un fichier `afac-decisions-fondateur.md` (décision gravée ailleurs).
- `creer_note_debit` : docstring périmée.

## 6. Couverture et sortie de cycle

- **Couvert.** 32 tâches sur 89 cochées ; 3 sondes jouées dans la pile locale.
- **Non couvert.** Les 57 autres tâches cochées ; aucun rejeu navigateur.
- **Statut.** 0 écart S1-S2 ⇒ troisième contre-visite consécutive à zéro : AFAC reste `vérifié`, hors cycle. Les quatre
  S3 (AFAC103-106) se construisent sans rouvrir le cycle.

## 7. Coût

- 4 vérificateurs opus (effort élevé) ≈ 0,79 M de jetons, 1 rédacteur ; aucun appel Fable (aucun S1).

<!-- verifie | groupe: AFAC | pct: 96 | ecarts_s1_s2: 0 -->
