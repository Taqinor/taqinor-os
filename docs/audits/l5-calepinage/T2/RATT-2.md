# RATT-2 — contre-vérification de rattrapage (compte rev_b5), tour 2, 23/11/2026

## 1. Verdict en trois lignes
- Sur 15 corrections sans preuve, 12 sont `ok`, 2 `partiel` (ACAL693, ACAL703, faute de donnée saisissable ou sourcée), 1 non essayée (ACAL1315).
- Aucune régression, aucun `faux`. Trois défauts nouveaux de gravité S2 croisés en chemin (mode météo « année type » qui bloque toute simulation, fiche module qui efface en silence dégradation et garantie, journée type coupée).
- Chaque verdict est écrit au fil de l'eau dans `registre/evenements/T2-RATT-2-cv.jsonl` (14 lignes, une par tâche jouée).

## 2. Comptes
ok 12 · partiel 2 · non-fait 0 · faux 0 · régression 0 · déjà-présent 0 · non essayé 1.
- ok : ACAL588, 596, 677, 577, 582, 895, 833, 444, 720, 738, 740, 767.
- partiel : ACAL693 (valeur de garantie à 10 et 25 ans non jouable : aucune saisie de fiche possible, T2-RATT-2-007), ACAL703 (pastille « inhabituel » non jouable : `data/plages_usuelles.json` ne porte aucune bande, « zéro chiffre inventé »).
- non essayé : ACAL1315 (voir § 5).

## 3. Constats neufs (`registre/constats/T2-RATT-2.jsonl`)
- T2-RATT-2-006 (S2) : mode météo « année type » (tmy) accepté par les réglages mais toute simulation est refusée en 409 (« série météo ne porte que l'irradiance horizontale »). Remis à « pluriannuel » aussitôt.
- T2-RATT-2-007 (S2) : POST/PATCH d'une fiche module avec dégradation et garantie : 200/201 mais les quatre valeurs reviennent à `None` sans message (le sérialiseur ne les expose pas). Bloque ACAL693 et le tableau pluriannuel.
- T2-RATT-2-008 (S2) : « Journée type » (Résultats > Production) : tracé de 640 px fixes dans un bloc de 235 px, moitié droite coupée (limite, pic de midi, légende).
- T2-RATT-2-003 (S3) : ligne dépliée du diagramme de pertes à 1440 : la citation de référence tient dans ~60 px, une quarantaine de lignes.
- T2-RATT-2-004 (S3) : mode Expert, onglet Résultats : tableau des pans coupé (« MUT » pour Azimut), panneau qui défile de côté.
- T2-RATT-2-005 (S3) : à 390 px, le bandeau « GPS du lead corrigé » se chevauche et sort de l'écran.
- T2-RATT-2-001 (S4) : bibliothèque, un lien « Partir de ce modèle » passe seul à la ligne.
- T2-RATT-2-002 (S4) : rapport PDF Hors réseau, mois écrits 1 à 12 au lieu de janvier à décembre.

## 4. Ce qui est bien
- Plan de pose (ACAL588) rendu hors ligne, sans ressource externe ni montant, avec étiquette de rangée, flèche de sens de pose et liste des chaînes ; refus propres (devis absent : `None`).
- Points de contrôle (ACAL596) dans l'ordre de l'affectation, omission nommée sans système de fixation.
- Boucle DC (ACAL677) : 4,5 m² exact sur l'exemple de la tâche.
- Traducteur serveur : bandes de coupure au millimètre de la formule, châssis 2 x 10 = 4 tables x 20 modules, refus nommé `zones.1.chassis` pour deux châssis différents (ACAL577, 582).
- Rapport d'étude : section « Hors réseau » complète (défaillance, pire mois, banque) et absente du raccordé (ACAL833) ; diagramme de pertes en lignes pleine largeur à 390 px sans défilement (ACAL444) ; semis des exemples idempotent avec badge « Exemple » et copie vers un lead (ACAL895) ; carte « simulation périmée » sans toast (ACAL767).

## 5. Non essayé, et pourquoi
- ACAL1315 : la spec `frontend/e2e/calepinage-maquettes.spec.js` écrit ses paires dans `frontend/test-results/` du dépôt servi (en lecture seule pour moi) et crée ses propres données ; non jouée, à confier à l'orchestrateur comme le dit sa preuve (PA2.3).
- Branche « 409 sur l'export automatique » d'ACAL767 : l'écran relit le résultat avant et n'appelle pas l'export ; non forçable.
- ACAL738 sans `p_dc_kw` : le CSV porte toujours la colonne sur cette pile.
- ACAL588 : cas « conception changée depuis l'acceptation » (devis accepté) non joué.

## 6. Pile : ce que j'ai fait et remis
Commandes de serveur (toutes `docker exec l5cal-django python manage.py …`) :
- `shell` (lecture seule) : `plan_pose_svg_pour_devis` et `points_de_controle_pose` sur les devis 2286 et 2308 ; `entree_depuis_layout` et `calepiner_pan_traduit` sur des documents de test construits dans le script (rien écrit) ; `specs_for_produit` ; listes de calepinages et de produits.
- `semer_exemples_calepinage --societe 7502` : dry-run (3 à créer), `--apply` (3 créés), `--apply` (0 créé), dry-run final. Changement d'état : 3 modèles « Exemple » ajoutés à la société de démonstration (visibles de tous).
Réglages société : `mode_meteo` mis à « tmy » puis remis à « pluriannuel » (deux fois) ; `fenetre_annees` mis à [2023, 2023] puis remis à [2014, 2023]. Relu après : mode « pluriannuel », fenêtre [2014, 2023], autres réglages inchangés. Une simulation lancée par un autre relecteur pendant ces fenêtres a pu être calculée avec le réglage temporaire ; plusieurs simulations sont aussi devenues « périmées » sans geste de ma part quand d'autres relecteurs changeaient des réglages ou des fiches.
Données créées (préfixe RATT-2) : leads 2549 à 2552 et suivants, calepinages 2019 (devis 2308, variante 367, système de fixation F2POSE-B choisi), 2020, 2024 (copie d'exemple), 2025 (hors réseau, batterie Dyness 16 kWh x2), 2026 et 2027 (Zagora), produits 22989 (module), 22991 (onduleur à déclassement 25 °C) et leurs fiches.

## 7. Propositions les plus fortes
1. Laisser saisir dégradation et garantie sur la fiche module (comme PVsyst, base de modules) : sans cela, le tableau pluriannuel et la garantie à 25 ans ne servent jamais.
2. Retirer ou réparer le mode « année type » des réglages de simulation : un choix proposé qui interdit toute simulation (référence : PVsyst, qui simule sur l'année type par défaut).
3. Donner au graphique « Journée type » la largeur de son conteneur, comme le diagramme de pertes : la courbe des panneaux au-dessus de la limite est le message principal de cet écran (référence : PVsyst, graphique de puissance de l'onduleur sur un jour).

Fichiers : `docs/audits/l5-calepinage/registre/evenements/T2-RATT-2-cv.jsonl`, `docs/audits/l5-calepinage/registre/constats/T2-RATT-2.jsonl`, scripts et captures dans `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/RATT-2/`.
