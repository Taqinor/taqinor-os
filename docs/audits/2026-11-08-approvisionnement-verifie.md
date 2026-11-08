# Vérifie AAPV — contre-visite de clôture du parcours PA6 « approvisionnement », 08/11/2026

Commande `loop audit` (reprise du 08/11). L'audit de parcours PA6 (06/11, PR #1296) avait déposé AAPV1-75 ; le groupe compte 67
tâches cochées sur 68 (AAPV60 ouverte, 98 %) : la clôture est due. La contre-visite n'a rien construit, n'a lancé aucun deploy,
n'a rien écrit en prod.

## 0. Préconditions

- **SHA.** `origin/main` = `76344a269`. Branche de claim : `verifie-aapv-0811`.
- **Registre.** PA6 `approvisionnement`, groupe AAPV, 68 tâches, 67 `[x]`.
- **Échantillon (graine = SHA `76344a269`).** Les 20 P0/P1 cochées + 12 tirées = **32 tâches**, 4 lots de 8.
- **Pile locale.** Le conteneur partagé tourne un ancien checkout et la base n'a pas les migrations AAPV : les sondes ne sont
  PAS rejouées ; chaque verdict repose sur le commit, le code sur `origin/main`, le test nommé et la CI verte du merge (#1299),
  recoupés avec les enregistrements d'acceptation `docs/audits/acceptation/AAPV/2026-11-08-*.md`.

## 1. Vérificateurs (4 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **31** | AAPV1-12, 15, 17-20, 22, 28, 34, 35, 37, 42, 43, 48, 54, 62, 68, 69, 70, 71 |
| partiel | **1** | AAPV16 (moitié serveur conforme ; l'écran affiche « [object Object] ») |
| non-fait / faux / régression | **0** | — |

## 2. Tests nommés

Tous présents dans un module existant et assertant le Then ; aucun test affaibli (ACHT14 réaligné décrivait le défaut, la
fixture ArbitrageRegleApprobationAchat passée admin suit la nouvelle autorisation). Le vitest d'AAPV16 mocke des chaînes au lieu
de la forme serveur : c'est la cause de l'écart. Aucun test rejoué en local (CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/AAPV/C-AAPV-040.py` (+ -L2) | AAPV1 | lecture : passerait à repro False sur `origin/main` |
| `docs/audits/sondes/AAPV/C-AAPV-043.py` | AAPV4, AAPV5 | lecture : resterait faussement REPRO (somme la retenue sur les paiements seuls) |
| `docs/audits/sondes/AAPV/C-AAPV-002.py`, `C-AAPV-021.py` (cas B) | AAPV9 | lecture : resteraient faussement REPRO (l'événement part à `on_commit`, non exécuté par la sonde) |
| `docs/audits/sondes/AAPV/C-AAPV-020.py`, `-023.py`, `-044.py`, `-049.py`, `-050.py`, `-106.py` | AAPV11, 37, 42, 43, 62, 35 | lecture : passeraient à repro False |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AAPV-VER1-020 | AAPV16 | S3 | l'écran BCF affiche « Prix à vérifier : [object Object] » : `texteAvertissementsPrix` stringifie des objets `{type, message}` servis par le serveur | STATIQUE (lecture) | AAPV72 |
| C-AAPV-VER1-001 | AAPV4, AAPV5 | S4 | la sonde 043 ne lit pas la retenue portée par l'imputation (code correct, sonde fausse au rejeu) | STATIQUE (lecture) | — (sonde à corriger au prochain rejeu) |

Aucun S1 : ni seconde lentille ni critique Fable (METHODE §C.4).

## 5. Optionnel (non déposé)

- Sondes 002 et 021 (cas B) : envelopper le `valider/` du retour dans `captureOnCommitCallbacks(execute=True)` avant tout rejeu.
- AAPV11 : la boucle d'écriture d'`annuler_receptions_brouillon_bcf` n'a pas son propre `atomic` (tient par l'appelant unique).
- AAPV17 : seul l'appel de cascade est atomique, `bc.statut = ANNULE` est enregistré avant (S4 au plus).
- AAPV16 : `creer_bcf_depuis_lignes` lit le produit sans filtre société ; « %% » dans l'avertissement « écart historique ».
- AAPV2 / AAPV3 : facture en devise et ventilation partielle (cas limites, non sondés).
- Preuves en direct jamais jouées : écran Qualité (AAPV37), « Annuler » BCF (AAPV62).

## 6. Couverture et sortie de cycle

- **Couvert.** 32 tâches sur 67 cochées ; lecture du code et des tests sur `origin/main`.
- **Non couvert.** Les 35 autres tâches cochées ; aucune sonde rejouée (pile locale sans les migrations) ; aucun rejeu navigateur.
- **Statut.** 0 écart S1/S2 ⇒ AAPV sort du cycle à la coche d'AAPV60 et d'AAPV72.

## 7. Coût

- 4 vérificateurs (opus, effort élevé) ≈ 0,85 M de jetons ; aucun appel Fable (aucun S1).

<!-- verifie | groupe: AAPV | pct: 98 | ecarts_s1_s2: 0 -->
