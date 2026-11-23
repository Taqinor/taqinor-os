# Rapport F2-POSE-a — tour 2 (chef d'équipe : panneaux, structure, lestage, plans d'équipe)

Compte `rev_pose`, pile `l5cal` (http://127.0.0.1:5241, `origin/main@bfb859c90`), bureau 1440 × 900, thème clair,
Chromium. Scripts et captures : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/T2/F2-POSE-a/`
(`cap/` pour les captures, `dl/` pour les PDF/SVG/DXF). Mes calepinages : 1959 (A, toit plat 10 × 7), 1960 (B, champ
au sol), 1962 (C, toit + champ au sol, lead industriel), 1965 (D) et 1966 (E) (Tiznit, obstacle), 1968 (F, 28 × 12 avec
coupure), 1970 (G, 28 × 12), 1973 (H, paysage). Deux systèmes de fixation créés (F2POSE-A, F2POSE-B). Le réglage de
lestage de la société a été saisi pour la preuve puis remis à vide (`GET parametres/` → `lestage: {}`, vérifié).

## 1. Verdict

L'étape Panneaux guidée a pris la forme de la maquette (blocs, cartes, lecteur) et les corrections de champ au sol, de
fixation et de lestage tiennent à l'écran. Mais la pose n'est pas encore digne de confiance : une pose remplie en mode
Expert est réaffichée autrement à la réouverture puis écrasée au premier enregistrement (S1), et les chiffres de
production changent sans que la pose change. Les réglages de structure (châssis, coupures, pieds) sont cachés et le
châssis N × M ne pave pas.

## 2. Contre-vérification (18 tâches)

| ok | partiel | non-fait | faux | régression | déjà-présent | non essayé |
|---|---|---|---|---|---|---|
| 9 | 7 | 0 | 0 | 0 | 0 | 2 |

- ok : ACAL606, ACAL609, ACAL607, ACAL608, ACAL559, ACAL560, ACAL572, ACAL576, ACAL579.
- partiel : ACAL610 (chiffre kWc illisible, chevauche le taux), ACAL1298 (aucune alerte d'ombre, PROCHE pas FIDÈLE),
  ACAL1295 (carte « Le plus de panneaux » vide tant qu'on ne la clique pas), ACAL1297 (pastille centrée, légende sans
  panneaux colorés), ACAL585 (champs enregistrés mais le pavage ne fait pas de châssis, aucune note), ACAL584 (Centre
  juste, mais Ctrl+Z ne défait rien et le choix ne revient pas à la réouverture), ACAL574 (refus réels, mais bouton pas
  grisé et motif seulement en infobulle).
- non essayé : ACAL577, ACAL582 (voir § 5).

Cases de matrice cassées :
- K-GESTE (Chromium souris, étape Panneaux) : molette, bouton −, plein écran, double-clic : pas de casse, aucune erreur
  de console. Glisser près d'un coin : une fois sur trois essais, le toit s'est déformé en trapèze et la pose est passée
  de 16 à 21 panneaux (`cap/s35-D-glisser.png`) ; non reproduit ensuite (position du coin différente à chaque
  chargement) → « à vérifier », pas au registre.
- K-DOC-GEOMETRIE : planche A3 portrait (modules 1,303 × 2,065 m projetés, debout) et paysage (2,384 × 1,128 m) justes,
  DXF portrait et paysage justes (aucun recouvrement, une seule TOITURE) : pas de casse sur ces quatre cases. Plan de
  câblage (409, électrique non réglé) et devis « toit + champ au sol » non joués.

## 3. Constats neufs (registre `constats/T2-F2-POSE-a.jsonl`)

- T2-F2-POSE-a-009 — **S1** — une pose remplie en Expert (60 panneaux, enregistrée) se rouvre à 5 panneaux, et
  « Enregistrer » écrase les 60 par 5 (rejoué sur deux calepinages).
- T2-F2-POSE-a-002 — **S2** — onglet Terrain : les cinq chiffres du champ au sol se chevauchent (« 93,7256.3 »).
- T2-F2-POSE-a-008 — **S2** — avec une cheminée de 3 m : pastille « 7 351 kWh / an · ≈ 21 % » contre « 7 351 · ≈ 75 % »
  sans cheminée, bande « Année 1 ~1 883 kWh/an » avec la même économie en MAD, aucune alerte d'ombre.
- T2-F2-POSE-a-010 — **S2** — la production d'une pose saute de +32 % à la réouverture (14 901 → 19 603 kWh/an).
- T2-F2-POSE-a-001 — S3 — même saut, plus petit, sur le toit simple (5 571 → 5 817 kWh/an).
- T2-F2-POSE-a-003 — S3 — tableau « Site » : le kWc du site n'est visible qu'en faisant défiler le tableau.
- T2-F2-POSE-a-004 — S3 — carte « Le plus de panneaux » vide avant clic ; après clic, l'autre carte perd son pourcentage.
- T2-F2-POSE-a-005 — S3 — légende « Ensoleillement de chaque panneau » mais panneaux toujours noirs.
- T2-F2-POSE-a-006 — S3 — lead industriel : « Aucune taille ne se tire des factures… Renseigner la facture » alors que
  la facture est saisie.
- T2-F2-POSE-a-007 — S3 — onglet Fixation : liste et bouton coupés au bord droit, « 13.24 m ».
- T2-F2-POSE-a-011 — S3 — retraits : libellés passés sous les valeurs (« d'extrémité0.5 »).
- T2-F2-POSE-a-012 — S3 — alignement des rangées : Ctrl+Z promis mais sans effet, note qui parle de 60 modules quand la
  carte en montre 5.
- T2-F2-POSE-a-013 — S3 — châssis, coupures et pieds cachés derrière « Déplacer les panneaux » (~4 600 px plus bas).
- T2-F2-POSE-a-014 — S3 — bandeau des quatre chiffres tassé ; 3,60 kWc ici contre 3,55 kWc dans la pastille.

## 4. Ce qui est bien (à ne pas casser)

- Champ au sol : entraxe anti-ombrage calculé à la latitude de l'épingle (5,9 m, 132 modules), alerte « Rangées trop
  serrées » avec bouton de retour au calcul, kWc juste (124,96 pour 176 × 710 Wc), tableau Site qui additionne toit et
  sol (139,36 kWc).
- Systèmes de fixation : formulaire complet, erreurs posées sous le bon champ (provenance, source du composant n° 2),
  liste de choix dans l'onglet Fixation, choix gardé au rechargement, nomenclature calculée.
- Lestage : écran unique, lien profond `#lestage-<clé>` qui met le focus sur la ligne, valeur gardée, onglet « Masse &
  lestage » inchangé (texte identique avant/après).
- Coupures du pavage : 8 + 8 + 2 exact, coupure réelle annoncée, champs revenus à la réouverture.
- Pieds du châssis : la portée saisie espace bien les pieds (6 → 4 sur 5 modules).
- Orientation portrait/paysage écrite dans le document, l'export JSON, la planche et le DXF.
- Pan existant : les gestes sont vraiment refusés, avec un motif qui nomme le pan.

## 5. Non essayé, et pourquoi

- ACAL577 et ACAL582 (compte du SERVEUR d'un pan à coupure ou à châssis) : aucun écran de l'atelier ni du devis
  n'affiche ce compte ni sa « phrase de règle » ; le traducteur ne tourne que dans le compte du devis, derrière un
  interrupteur et des réglages de dégagement de la société. Je ne l'ai pas joué depuis l'interface.
- Devis « toit + champ au sol » : « Générer le devis » ouvre la liste « Prêt à envoyer ? » (5 points électriques à
  régler) ; ce parcours appartient aux relecteurs Électrique et Documents.
- Plan de câblage DXF : 409 tant que l'électrique n'est pas réglé.
- WebKit (iPhone, iPad), thème sombre, tablette : non joués (mon axe : bureau clair).
- Lisibilité sur une vraie photo aérienne : fond gris sur cette pile.
- À vérifier (vu une fois, pas reproduit) : un glisser qui commence près d'un coin du toit, à l'étape Panneaux guidée,
  déforme le toit et repose les panneaux (`cap/s35-D-glisser.png`, 16 → 21). Un essai de « vider » les champs du châssis
  (les quatre champs effacés puis Tab) n'a pas retiré `chassis` du document enregistré (`lay-G-centre.json`) : à
  rejouer avant d'en faire un constat. Un plantage de page Chromium au rechargement de Réglages n'a pas été reproduit
  (trois rechargements propres ensuite) : cause environnementale probable.

## 6. Trois propositions

1. **Une rubrique « Structure et pose » visible sans outil de déplacement** (fonction + simplicité) — système de
   fixation, châssis N × M, coupures, portée des pieds, lestage et nomenclature au même endroit, avec la nomenclature
   en sortie directe : c'est l'organisation de **K2 Base** (on choisit le système, la structure se dessine et la liste
   de pièces se met à jour). Aujourd'hui ces réglages sont dispersés entre l'onglet Fixation, l'onglet Masse & lestage,
   l'écran Réglages et le panneau « Déplacer les panneaux ».
2. **Une seule production par pose, et la pose enregistrée toujours rouverte telle quelle** (fonction) — comme
   **OpenSolar**, dont la pose automatique propose des variantes mais ne remplace jamais en silence ce qui est
   enregistré. Corriger 009 puis afficher un seul kWh/an (pastille, cartes, bande, Résultats).
3. **Panneaux colorés par leur ensoleillement et alerte d'ombre nommée** (beauté + fonction) — la maquette v2
   `Panneaux.dc.html` le montre (panneaux jaunes à gris, « 2 panneaux à l'ombre de la cheminée », boutons Retirer /
   Garder) et **OpenSolar** colore aussi chaque module ; ici les panneaux sont noirs et l'ombre d'une cheminée de 3 m
   ne déclenche aucune alerte.
