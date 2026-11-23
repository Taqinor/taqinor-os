# Tour 2 — S2-PARCOURS-b (contre-vérification de 25 corrections, compte `rev_couture`, bureau 1440 × 900 clair)

Instrument http://127.0.0.1:5241 (`origin/main@bfb859c90`). Scripts et captures :
`C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/S2-PARCOURS-b/` (`cap/`).
Mon calepinage : 1927 « S2-PARCOURS-b Villa Casablanca » (lead 2458, toit plat 12 × 8 m, 4 panneaux Canadian Solar 710 W, Huawei 5 kW).

## 1. Verdict

Les corrections jouées tiennent à l'écran : la porte « Visite technique validée », la cohérence kWc, l'obstacle qui dépasse, la compatibilité
matériel, l'écart PVGIS avec son voyant, la liste d'erreurs de réglages et les favoris du catalogue font ce qu'elles promettent.
Deux restes : le « ? » du P90 écrit « valeur non publiée kWh » quand la valeur manque, et la limite de modules d'ACAL890 n'est pas committée.
La revue s'est arrêtée à mi-liste : le serveur Django de l'instrument (8021) ne répond plus depuis ~20 min (tout appel API, même sans jeton,
expire ; le front `/login` répond). Je n'ai rien relancé (règle 2 de la fiche).

## 2. Comptes (25 corrections)

ok 9 · partiel 1 · non-fait 1 · faux 0 · régression 0 · déjà-présent 0 · non essayé 14.

- ok : ACAL854, 855, 857, 859, 862, 863, 906, 947, 960 (857 et 890 ont chacun deux lignes identiques au registre, sans effet).
- partiel : ACAL873 — tuiles, écart PVGIS et mois ont leur « ? » ; le P90 écrit « ici valeur non publiée kWh » ; « ? » de la cascade non vérifiés.
- non-fait : ACAL890 — `frontend/e2e/calepinage-perf.limite.json` absent du code servi et de la branche de revue (aucune limite mesurée).
- non essayé : ACAL874, 875, 877, 878, 879, 880, 883, 884, 885, 888 (serveur tombé avant que je les joue, ou bloqué à la création de variantes),
  ACAL891 (demande une limite basse injectée : impossible sur un front construit, et sans fichier de limite le refus est inerte),
  ACAL894 (PVGIS ne peut pas être coupé depuis la pile), ACAL897 (photo calée à produire + fond de carte absent), ACAL959 (modèle et lead d'Agadir non préparés).
  Soit 14 non essayés : 874, 875, 877, 878, 879, 880, 883, 884, 885, 888, 891, 894, 897, 959. Total 9 + 1 + 1 + 14 = 25.

## 3. Preuves (une ligne par verdict qui n'est pas simple)

- ACAL857 ok : avec « visite exigée » activée quelques secondes sur la société (`presets`, remis à `{}`), l'écran Documents montre « Visite technique validée — Non validée » en rouge et « Approbation à jour — Non évaluée tant que la visite n'est pas validée » (`cap/t857-docs.png`).
- ACAL862 ok : document réécrit par l'API à 3,20 kWc : « le document annonce 3,20 kWc, la fiche des modules donne 2,84 kWc » en orange ; remis à 2,84 (vert). Pas de bouton « Régler » sur cette ligne malgré le geste « Enregistrer le calepinage ».
- ACAL863 ok : obstacle « chien-assis » sur la rive : orange « Chien-assis / lucarne dépasse du pan Zone 1 » (le pan s'appelle « Zone 1 », pas « A »).
- ACAL906 ok : Huawei 10 kW triphasé : « Compatible sous réserve » orange, raisons derrière le « ? » (courant d'entrée MPPT) et pas sur la ligne.
- ACAL854/855/859 ok : +17,2 % ; sans tolérance « écart publié sans verdict — la tolérance n'est pas réglée » ; tolérance 5 % orange nommée avec lien « voir les pertes » ; 20 % vert ; la ligne « Écart avec PVGIS » du « prêt à envoyer ? » passe à « à régler » (« 17,19 % pour 5,00 % admis »). Tolérance retirée ensuite.
- ACAL947 ok : trois clés fautives (LID `{"mono": 2}`, Uc/Uv texte, seuil DC/AC texte) : UN seul 400 les nommant toutes, liste sous « Enregistrer les réglages », chaque ligne mène à `#calx69-<clé>`, saisies gardées (`cap/s13-947-erreurs.png`).
- ACAL960 ok : deux listes à cocher Modules/Onduleurs, enregistrées sous `modules`/`onduleurs`, étoile en tête dans Matériel électrique (`cap/s15-favoris-coches.png`). Favoris remis à `{}`.

## 4. Constats neufs (`registre/constats/T2-S2-PARCOURS-b.jsonl`, 4)

- 001 S4 — Réglages : le toast générique « Une erreur est survenue. » s'ajoute à la liste d'erreurs ; la liste répète libellé puis clé brute.
- 002 S3 — Production : le « ? » du P90 lit « ici valeur non publiée kWh » ; tuiles P75/P90/P95 tronquées dans la colonne de 340 px.
- 003 S4 — « produirait environ 5 905,7 kWh par an une année moyenne » (il manque « pour »).
- 004 S3 — Production : « FicheTechnique.degradation_annuelle_pct » affiché dans une phrase métier.
- Non enregistré (vu en passant, non prouvé) : l'enregistrement du matériel électrique est resté sur « Enregistrement… » plus de 5 s au premier essai, sous charge.

## 5. Ce qui est bien

Le panneau « Prêt à envoyer ? » de Documents (états rouge/orange/vert, bouton « Régler dans … », légende) ; les valeurs servies dans les « ? » de la production ; l'API de réglages qui refuse en une fois avec la forme `{section: {clé: motif}}`.

## 6. Non essayé, et pourquoi

Voir §2. Cause commune : le serveur Django de l'instrument est tombé (aucune réponse, y compris sur 127.0.0.1:8021) après mes essais de simulation ; les autres relecteurs partagent la même pile. Je n'ai pas relancé les simulations de variantes (ACAL883/884).

## 7. Écritures partagées faites puis remises (société de démonstration commune)

Réglages `tolerance_validation_pct` (posée 5 % puis 20 %, retirée par `null` : GET identique à l'original), `favoris_materiel` (remis `{}`), `presets` (feu vert/approbation exigés pendant ~10 s, remis `{}`). Sur mon calepinage 1927 : `result.kwc` et un obstacle réécrits par l'API puis restaurés ; `entree-electrique` remise sur Huawei 5 kW. Aucun lead ni calepinage d'autrui touché.

## 8. Propositions

1. Le « ? » d'une valeur non publiée dit « non publiée » seul, sans unité (PVsyst : cellule vide + note).
2. La ligne du « prêt à envoyer ? » qui devient orange porte sa raison sous le titre, pas seulement derrière le « ? » (Reonic « Check before you send »).
3. Livrer le fichier de limite mesurée (ACAL890) pour que le refus d'ACAL891 existe vraiment.
