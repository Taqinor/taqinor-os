# Vérifie ADEV — contre-visite de clôture du groupe devis (J1b), 04/11/2026

Commande `loop audit` (reprise du 04/11). Le groupe compte 97 tâches cochées sur 99 (ADEV46 et ADEV66 ouvertes, 98 %) : la
clôture (≥ 95 %) est due ; la précédente contre-visite était celle de mi-parcours du 11/10 (0 S1-S2). La contre-visite n'a
rien construit, n'a lancé aucun deploy, n'a rien écrit en prod. Pile locale partagée ; chaque sonde tourne en transaction
annulée.

## 0. Préconditions

- **SHA.** `origin/main` = `fcbed3760`. Branche de claim : `verifie-adev-0411`.
- **Registre.** J1b `devis`, groupe ADEV, 99 tâches, 97 `[x]`.
- **Échantillon (graine = SHA `fcbed3760`).** Les 16 P0/S1 cochées + 20 tirées = **36 tâches**, 4 lots de 9.
- **Déjà déposé, non redéposé.** Audit de parcours PA3 devis → signature (ADVS) et sa contre-visite du jour
  (`docs/audits/2026-11-04-devis-signature-verifie.md`) ; contre-visites AMOT et ACHT du même jour ; ADEV46 (ouverte).

## 1. Vérificateurs (4 lots de 9, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **29** | ADEV2, 8, 16, 25, 27, 28, 30, 31, 38, 42, 50, 51, 52, 55, 58, 72, 76-80, 82, 84-86, 89, 92, 95, 96 |
| partiel | **6** | ADEV32, 44, 81, 91 (jumeau oublié), ADEV24 et ADEV67 tiennent mais leur test est plus étroit que la tâche |
| régression partielle | **1** | ADEV9 (une vente acceptée puis révisée sort des acceptés du tableau de bord) |
| non-fait / faux | **0** | — |

ADEV28, partiel le 11/10, est soldé (volet C&I testé par ADEV75). ADEV79 : le volet « structure et câbles hors total » est
remplacé par la décision fondateur du 26/10 (devis préliminaire chiffré « à confirmer ») ; pas un écart.

## 2. Tests nommés

Tous présents dans un module existant. Tests faibles relevés : ADEV24 (3 chemins de numérotation sur 8), ADEV67 (agricole
seul), ADEV96 (source mockée — levé par la sonde VER4-012). Aucun test rejoué en local (CI d'abord) ; garde ADEV72 rejouée
verte.

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ADEV/C-ADEV-VER4-010.py` | ADEV81 | REPRO : aperçu C&I du générateur « retour 1 an » sur trois articles sans prix |
| `docs/audits/sondes/ADEV/C-ADEV-VER4-011.py` | ADEV9 | REPRO : V1 acceptée puis « Réviser » ⇒ acceptés 1 → 0 au tableau de bord |
| `docs/audits/sondes/ADEV/C-ADEV-VER4-012.py` | ADEV96 | conforme : empreinte signable réelle, stable, sensible à l'étude seule |
| `docs/audits/sondes/ADEV/C-ADEV-VER4-020.py` | ADEV32 | REPRO : l'origine d'un devis d'upsell (référence chantier) servie en note client |

## 4. Écarts retenus (S3 seulement)

| C-id | Tâche d'origine | Écart | Sonde | Tâches |
|---|---|---|---|---|
| C-ADEV-VER4-010 | ADEV81 | l'aperçu C&I du générateur calcule un retour sur un investissement incomplet (le PDF, lui, le dit non chiffré) | REPRO | ADEV106 |
| C-ADEV-VER4-011 | ADEV9 | tableau de bord Quote-to-Cash et kWc signés lisent `is_active` : une vente révisée disparaît | REPRO | ADEV107 (après ADEV46) |
| C-ADEV-VER4-020 | ADEV32 | origine d'upsell écrite dans la note client (page publique et PDF) au lieu du chatter | REPRO | ADEV108 (test chantiers), ADEV109 |
| C-ADEV-VER4-030 | ADEV44 | la fenêtre « Refuser » propose les motifs archivés, que le serveur refuse | STATIQUE | ADEV110 |
| C-ADEV-VER4-031 | ADEV91 | le générateur refuse d'enregistrer un devis C&I dont la consommation vient d'une facture en MAD ou d'un relevé partiel | STATIQUE | ADEV111 |

Aucun S1 ni S2 : ni seconde lentille ni critique Fable (METHODE §C.4).

## 5. Optionnel (non déposé)

- ADEV50 : le titre « Vos économies » de la page publique ne suit pas la bascule d'option (chiffre juste pour l'option affichée).
- ADEV80 : fenêtre de quelques millisecondes entre la libération du verrou et l'écriture du rejeu.
- `imports.py::creer_devis_import` écrit « Migré (réf. source …) » dans la note client (S4, même classe qu'ADEV109).
- `views/devis_cycle.py::refuser` : `abandonner_revision` appelée après le commit du refus.
- `theme.marques_correction` n'imprime qu'en français.

## 6. Couverture et sortie de cycle

- **Couvert.** 36 tâches sur 97 cochées ; 4 sondes jouées dans la pile locale.
- **Non couvert.** Les 61 autres tâches cochées ; aucun rejeu navigateur (page `/proposition` d'ADEV95, cas mono d'ADEV86).
- **Statut.** 0 écart S1-S2 à la clôture : première clôture à zéro ; ADEV sort du cycle à la prochaine clôture à zéro
  (deux consécutives). Les S3 (ADEV106-111) se construisent sans rouvrir le cycle.

## 7. Coût

- 4 vérificateurs (opus, effort élevé) ≈ 0,9 M de jetons ; 1 rédacteur ; aucun appel Fable (aucun S1).

<!-- verifie | groupe: ADEV | pct: 98 | ecarts_s1_s2: 0 -->
