# Audit des verdicts `ok` — lot D-3 (relecteur B2, beauté), 23/11

Liste : `T2/cv/AUDIT-OK-D-3.md` (6 verdicts). Lignes : `registre/evenements/T2-audit-ok-D-3.jsonl`.
Méthode : texte complet de la tâche, ligne de verdict B2 (sans champ `preuve`, `reste` vide) et rapport `T2/B2.md`,
captures ouvertes sous `scratchpad/T2/B2/cap/`, mesures `mesures-reel-bureau.json`, et pour les « fini quand »
statiques un `git grep` sur `bfb859c90` (le code rejoué).

**Comptes : confirmé 5 · insuffisant 1 · contredit 0.**

| Relecteur | conf. | insuf. | contr. |
|---|---|---|---|
| B2 | 5 (ACAL966, 427, 430, 438, 503) | 1 (ACAL963) | 0 |

## Insuffisant (1)
- **ACAL963** : `s20-bibliotheque.png` fait 1 440 × 900 (pas pleine page) et s'arrête aux cartes Presets, Kits,
  Modèles et Favoris. La carte « Courbes de consommation… », la mention « Profil de départ de l'application — une
  hypothèse, jamais une mesure… » et le badge « Profil de départ » ne sont pas visibles. La sortie du test regex de
  `s20_divers.js` n'a pas été gardée. À rejouer : Bibliothèque déroulée jusqu'à un profil de départ
  (`hypothese_interne`), avec capture de la mention et du badge et preuve qu'aucun texte rendu ne contient
  `CAL\d+`, `.py`, « dépôt » ni « HYPOTHÈSE INTERNE ». Le code (5 sous-titres) est conforme à `bfb859c90`.

## Remarques (sans rétrogradation)
- ACAL427 : les e2e de la clause « Preuve » n'ont pas été rejoués. Le « fini quand » (0 classe L dans les 5
  fichiers) est vérifié par `git grep`.
- ACAL503 : rayon des boutons à 2 px (T2-B2-004) et libellés des retraits qui chevauchent (T2-F2-POSE-b-004). Ces
  constats existent déjà ; ils relèvent du style ou d'autres tâches, pas du « fini quand ».
