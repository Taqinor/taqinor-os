# Vérifie AACQ — contre-visite de clôture du groupe acquisition (J0), 04/11/2026

Commande `loop audit` (reprise du 04/11). Les écarts du 01/11 (AACQ107 S2, AACQ108 S3) sont cochés : 72 tâches sur 72, la
clôture est de nouveau due. La contre-visite n'a rien construit, n'a lancé aucun deploy, n'a rien écrit en prod, n'a appelé
ni Meta ni Odoo. Pile locale partagée ; chaque sonde tourne en transaction annulée.

## 0. Préconditions

- **SHA.** `origin/main` = `8fb8ba32b`. Branche de claim : `verifie-aacq-0411`.
- **Registre.** J0 `acquisition`, groupe AACQ, 72 tâches, 72 `[x]` ; aucune tâche n'y porte un marqueur P0/S1.
- **Échantillon (graine = SHA `8fb8ba32b`).** AACQ107-108 (écarts du 01/11) + 18 tirées (25 %) = **19 tâches**, 3 lots.
- **Déjà déposé, non redéposé.** Contre-visites ACHT et AANA du même jour.

## 1. Vérificateurs (3 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **18** | AACQ6, 11, 13, 14, 17, 18, 20, 22, 31, 32, 62, 73, 95, 101, 102, 103, 107, 108 |
| partiel | **1** | AACQ38 (liste fermée d'hébergeurs : la promesse « jamais doublon » n'est pas tenue hors de la table) |
| non-fait / faux / régression | **0** | — |

Écarts du 01/11 : AACQ107 fermé (sonde VER-301 rejouée : ressaisir la même valeur pose la devise), AACQ108 fermé (seuil saisi
dans la devise du compte). AACQ31 : texte vieilli (depuis AACQ97, l'alignement Odoo ne fait que rapporter). AACQ95 : décision.

## 2. Tests nommés

Tous présents dans un module existant. AACQ6 : test à source simulée, levé par la sonde VER4-001 sur un chantier réel.
AACQ62 : `actions.pending` simulé au lieu de la couche HTTP. Aucun test rejoué en local (CI d'abord) ; garde AST d'AACQ103
rejouée sur 132 fichiers : 0 division hors de `cout_par_lead`.

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/AACQ/C-AACQ-VER-301.py` (01/11) | AACQ107 | fermé (ne se reproduit plus) |
| `docs/audits/sondes/AACQ/C-AACQ-VER4-001.py` | AACQ6 | conforme : photo d'un autre client refusée, `client_id` figé |
| `docs/audits/sondes/AACQ/C-AACQ-VER4-010.py` | AACQ38 | REPRO : deux boutiques e-monsite distinctes classées « doublon » |

## 4. Écarts retenus (S3 seulement)

| C-id | Tâche d'origine | Écart | Sonde | Tâche |
|---|---|---|---|---|
| C-AACQ-VER4-010 | AACQ38 | clé de doublon de la veille coupée à 2 labels pour tout hébergeur hors lexique (e-monsite, webnode, jimdo…) et pour les suffixes publics à deux labels | REPRO | AACQ109 |

Aucun S1 ni S2 : ni seconde lentille ni critique Fable (METHODE §C.4). Le pilote de veille n'est pas encore vivant
(VEIL41-46 BLOCKED).

## 5. Optionnel (non déposé)

- `views.py` (mots-clés) : `propose_keyword_hides` crée des actions sans proposeur ; avec le quatre-yeux actif, celui qui
  clique peut les approuver lui-même (à trancher si ce chemin doit compter comme humain).
- AACQ101 : si `GET /connection/` échoue, la devise retombe sur MAD et l'alerte de devise est fausse.
- Divisions coût / résultat hors `cout_par_lead` (rapports, règles, métriques), non libellées « coût par lead ».
- AACQ73 : `VeilleDecouverte.jsx` lit encore `detail` à la main (hors Files de la tâche).

## 6. Couverture et sortie de cycle

- **Couvert.** 19 tâches sur 72 cochées ; 3 sondes jouées dans la pile locale.
- **Non couvert.** Les 53 autres tâches cochées ; aucun rejeu navigateur ; AACQ6, 13, 14, 17 restent dans la dette
  d'acceptation gelée.
- **Statut.** 0 écart S1-S2 à la clôture : AACQ sort du cycle si la clôture suivante est elle aussi à zéro. AACQ109 se
  construit sans rouvrir le cycle.

## 7. Coût

- 3 vérificateurs (opus, effort élevé) ≈ 0,5 M de jetons ; aucun appel Fable (aucun S1).

<!-- verifie | groupe: AACQ | pct: 100 | ecarts_s1_s2: 0 -->
