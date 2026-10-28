# CCAT — critique Fable pré-merge rounds 2+3 (branche claude/ci-ccat-r3 @ c54b9c0b0) — À CORRIGER PAR LE PC2 AVANT LE PUSH

Rendue le 28/10 après la passation. 5 bloquants, puis libellés optionnels.

## Bloquants
1. **CI rouge `check_api_shapes.py` (stage-names)** : `docs/api-contracts.md est en retard sur le code` (2 @action neuves `pret-devis-ci`, `pret-devis-agricole`, views/produit.py ~l.1387-1405). Correctif : `python scripts/check_api_shapes.py --write`, relire le diff, commiter.
2. **« Compléter la fiche en Stock » ne fait rien depuis /stock** : `CatalogueTable.jsx` ~l.202-204 lit `?ci=a_completer` SEULEMENT dans l'initialiseur `useState` ; l'encadré est monté sur /stock, le clic change l'URL sans remonter → filtre jamais ouvert (le test monte directement avec l'URL). Correctif : `useEffect` sur `paramsUrl` qui ouvre le filtre (+ test : clic dans l'encadré ⇒ filtre actif).
3. **Agricole : « à compléter » renvoie au filtre C&I**, qui ne contient aucun article agricole (`pret_devis_agricole.py` ~l.27 réutilise `_poste` → `/stock?ci=a_completer` ; `produitCiACompleter` exige `etat_ci`). Le filtre « Pompage à compléter » existe (`CatalogueTable.jsx` ~l.187) mais n'est pas piloté par l'URL. Correctif : lien `/stock?pompage=a_completer` pour le segment agricole + câblage du paramètre comme `ci`.
4. **« ok » faux sur la pompe : type non contrôlé.** Le moteur `core/pompage/selection.py::choisir_pompe` (~l.356, 408) exige `type_produit(p) == 'immergee'` (défaut) ; une pompe sans `type_pompe` ni « immerg » dans le nom n'est jamais candidate. `_pompes` (pret_devis_agricole.py ~l.71-89) l'ignore ; la fixture `test_catalogue_complet_est_pret` (« Pompe tri complète », sans type) affirme `pret=True` alors que le moteur refuserait. Correctif : motif « type de pompe (immergée / surface) non renseigné » quand `type_produit(e) is None` ; réaligner la fixture. (Secondaire : variateur non scindé 220/380 V, `champ.py` ~l.193.)
5. **Migration 0175 trop étroite** : `ANCIENNE` ne couvre que la variante post-20/08 ; la variante semée le 12/06 (« …SG, rendement max ≈ 97,6 % … < 4 ms », commit 2cac38216) reste sur toute base semée avant le 20/08 (deploy lance seed_catalogue sans `--reappliquer-fiches`). Correctif : filtrer `description__startswith('Onduleur hybride Deye SUN-…SG')` et remplacer la SEULE 1re ligne (réversible par le même préfixe) ; test avec les deux variantes.
Écart de spec mineur : `PRESTATIONS` recopié dans `pret_devis_ci.py` ~l.20-23 → importer `parametres.serializers_company.FORFAITS_CI_PRESTATIONS`.

## Libellés (optionnel)
1. `PretDevisCi.jsx` ~l.23 `'Prestations (Paramètres)'` → `'Prestations'` (l'agricole se règle sur la fiche Stock).
2. ~l.42 badge `recommandé` → `facultatif`.
3. ~l.153 `Agricole (prêt)` / `Agricole (3)` → `Agricole — prêt` / `Agricole — 3 à compléter`.
4. `pret_devis_agricole.py` ~l.147 → `Installation pompage (prix fixe + prix par panneau, sur la fiche Stock de l'article)`.
5. ~l.33 → `le devis retient d'abord un autre article « Installation pompage » (le premier chiffré)`.
6. ~l.32 `barème fixe / par panneau non saisi` → `prix fixe et prix par panneau non saisis sur la fiche`.

## Vérifié OK par Fable
Semis à prix vide, Nexans seulement si vide ; références Deye = modèles confirmés fondateur ; ProduitForm 2 328 → 2 328 lignes ; views/produit.py 1 971 ; payload Paramètres inchangé ; unicité (company, nom) respectée ; flake8, import-linter 21/21, eslint, vitest 71/71, node 24/24, choices/filtre/cablage/ancres/forme_code/roles_mirror verts ; 0175 libre sur origin/main (dernière = 0174).
