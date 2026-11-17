# Critique visuelle de l'Agenda (L3 n°8, contradiction)

J'ai ouvert les 32 captures `agenda-*` et les 2 références. Mesures : pixels lus par script dans les PNG (iPhone en ×2).

## Jour — 6,5/10 (iPhone 6, bureau 7,5)
**À préserver.** L'heure courante (trait azur, point, « 10:05 » à la place de l'étiquette d'heure). ERP = gris + icône ;
tâche = teinte + case + filet. Bloc de 30 min sur une ligne (titre + heure). Chevauchement côte à côte sur bureau. Grille
fine, sans demi-heure : on ne pense pas à un tableur.
- **MAJEUR J1** (`agenda-jour-iphone-*`) : le haut de l'écran prend environ 285 pt avant 08:00 ; la grille garde 412 pt
  (4,7 h). **Correction** : bande « Toute la journée » en UNE rangée de puces de 36 pt défilante (« +2 » au bout), sans la
  ligne « Mardi 24 novembre » (redite du ruban). Gain : environ 80 pt, soit 5,6 h visibles.
- **MAJEUR J2** (`agenda-jour-iphone-clair/sombre`) : le + recouvre « Appeler un candidat ». **Correction** : voir T4.
- **MINEUR J3** : l'étiquette « Toute la journée » est à 2 pt du bord (heures à 13 pt) ; sur bureau, à 10 px pour une
  gouttière de 24. **Correction** : l'aligner sur la colonne des heures.
- **MINEUR J4** (`*-sombre`) : fond du bloc fait (30, 27, 25), gris chaud et boueux sur le marine (15, 20, 33) ; l'ambre
  (51, 39, 12) vire au brun. **Correction** : un bloc fait n'a pas de fond (filet et titre barré en gris seulement).
- **MINEUR J5** : le bloc fait de 08:00 à 10:00 mange 40 % de la fenêtre iPhone. **Correction** : ouvrir sur l'heure
  courante − 30 min.

## Semaine — 7/10 (iPhone 8,5, bureau 6)
**À préserver.** Sur iPhone, la liste façon Fantastical (« 3 tâches · 3 h 30 », heure, point, repère ERP, lundi barré,
aujourd'hui en rond plein, « Planifier ma semaine » dans la barre) : une vraie vue d'ensemble, pas un décor.
- **MAJEUR S1** (`agenda-semaine-bureau-*`) : la colonne du jour (244, 246, 251) a la teinte du week-end (245, 247, 251) ;
  en sombre (26, 32, 52) contre (30, 36, 50). Deux idées opposées, une seule forme. **Correction** : colonne du jour sans fond.
- **MAJEUR S2** (bureau) : le week-end vide prend environ 290 px pendant que des titres sont coupés (« Appeler le
  fournisseu… ») et que « Appeler… » (68 px) devient illisible. **Correction** : un jour non travaillé vide fait 64 px ; les
  blocs qui se chevauchent passent en cascade (le second à 60 % de la largeur, décalé de 40 %).
- **MINEUR S3** (iPhone) : la ligne annonce « 6 tâches » et en montre 2. **Correction** : 3ᵉ ligne « + 4 autres ».
- **MINEUR S4** (iPhone) : la barre grise sans légende se lit comme une progression. **Correction** : la retirer de
  Semaine ; elle ne vit que dans Planifier.
- **MINEUR S5** (iPhone) : le week-end en deux cartes (les autres jours sont à plat), et le + touche « dim. 29 ».
  **Correction** : une ligne à plat « sam. 28 – dim. 29 · jours non travaillés ».
- **MINEUR S6** (bureau) : la puce « Payer l'assurance » porte un drapeau, qui signifie priorité haute (spec 8 §4), et les
  échéances dans l'agenda sont un réglage AVANCÉ (spec 7). **Correction** : la retirer par défaut.
- **MINEUR S7** : « Mes projets » est replié en Semaine et déplié en Jour, l'inverse de la spec 7. **Correction** :
  l'inverser.

## Planifier ma semaine (choisie et posée) — 6/10 (iPhone 5, bureau 7)
**À préserver.** La consigne qui nomme la tâche en gras, avec × ; la tâche choisie cerclée ; le jour posé qui s'allonge du
titre ; le lundi passé désactivé. Sur bureau : colonne de dépôt cerclée avec la charge en tête, « Terminer » en or.
- **MAJEUR P1 — la charge projetée ment** (`agenda-semaine-planifier-iphone-*`, mesuré : 126 px = 4 h). Mer. : 2 h 30 + 2 h
  = 4 h 30, mais le fantôme s'arrête à 47 px (1 h 30), sans ambre. Mar. : 4 h + 2 h = 6 h, rien ne s'affiche. Seul jeu.
  signale le dépassement ; c'est pareil sur bureau. **Correction** : sur chaque jour cible, échelle de 6 h avec un repère à
  4 h, fantôme non plafonné, ambre au-delà de 4 h, une seule tournure (« 4 h 30 pour 4 h », celle de la spec 7) au lieu de trois.
- **MAJEUR P2** (iPhone) : partout ailleurs, « + » veut dire Ajouter ; ici, il veut dire « poser ». **Correction** : retirer
  les + ; toute la ligne est la cible.
- **MAJEUR P3** (iPhone) : un même jour prend trois formes (à plat en Semaine, cerclé d'azur, carte grise) : 7 boîtes
  (faute 1), et les cibles portent le contour de la tâche choisie. **Correction** : lignes à plat ; cibles sur fond
  `--tch-selection` sans bordure ; la tâche choisie, seule cerclée.
- **MAJEUR P4** (`…-pose-iphone-*`) : « Placée jeu. 26 · Annuler » s'affiche en haut (66–110 pt), loin du pouce. Le rapport
  dit « à la place de la consigne », l'image le contredit. **Correction** : le placer dans le volet, à la place de la consigne.
- **MINEUR P5** (bureau) : les projets sont coupés (« Chantier … », « Administ… »). **Correction** : S2, plus une ligne
  dédiée au point et au nom du projet.
- **MINEUR P6** : le non travaillé prend trois formes (carte grise, colonne blanche cerclée, teinte). **Correction** :
  `--muted` à 50 %, sans bordure, partout.

**« Toucher puis poser » : à garder** (plus sûr que glisser au doigt). On le comprend aujourd'hui seulement par la consigne.
Le + qui dit « ajouter », des cibles habillées comme la sélection et une charge fausse brouillent l'évidence. Une fois P1 à
P4 corrigés, la tâche est seule cerclée, les jours s'éclairent, chacun annonce sa charge, et le geste se lit sans texte. Non
vérifié sur un vrai iPhone.

## Mois — 8/10
**À préserver.** Cellules de 44 pt, panneau du week-end, « Férié » teinté comme le non travaillé, aujourd'hui cerclé,
jour choisi plein, liste en ligne de référence ; titres et passé atténué sur bureau. Utile : jours libres, fériés, charge.
- **MINEUR M1** : le « – » après 3 points se lit comme un 4ᵉ signe. **Correction** : « +2 », en gris.
- **MINEUR M2** (bureau) : deux colonnes de week-end vides de 200 px. **Correction** : S2.
- **MINEUR M3** : sans jour touché, seule la couleur nomme le projet (faute 11, légère). **Correction** : ouvrir avec
  aujourd'hui sélectionné.

## À venir — 7/10 (iPhone 8, bureau 5,5)
**À préserver.** « Demain · mer. 25 », la ligne de référence, les plages vides repliées.
- **MAJEUR V1** (`agenda-a-venir-bureau-*`) : une colonne de 710 px centrée, 360 px vides de chaque côté, sans le panneau
  « À placer » : un téléphone étiré. **Correction** : la mise en page du Jour (liste à gauche, panneau de 340 px à droite).
- **MINEUR V2** (iPhone) : sans « Aujourd'hui », les segments s'élargissent et « Jour » glisse de 100 à 123 px.
  **Correction** : des segments de largeur fixe dans les 4 vues.
- **MINEUR V3** : « échéance ven. 27 · sans jour » s'affiche par défaut alors que c'est un réglage AVANCÉ. **Correction** :
  le masquer.
- **MINEUR V4** : deux espaces dans « Demain  · mer. 25 ». **Correction** : une seule.

## Placer à une heure (choisie et durée) — 7,5/10
**À préserver.** Puce choisie cerclée ; « Placée à 14:00 · Annuler » avec 30 min / 1 h / 2 h ; bulles d'heure sur bureau.
- **MINEUR H1** : « + 12:00 » ne dit pas la durée d'une tâche d'1 h. **Correction** : « + 12:00 – 13:00 ».
- **MINEUR H2** : la consigne recouvre la pastille de 15:00. **Correction** : ajouter sous la grille un espace égal à la consigne.
- **MINEUR H3** : « 11:00 » est coupé en haut. **Correction** : caler le défilement sur une heure pleine.
- **MINEUR H4** (`…-duree-bureau-*`) : pas de « Placée à 14:00 · Annuler » après le dépôt. **Correction** : le même
  message, en bas à droite.

## Les écarts assumés par l'auteur
1. **88 px par heure : GARDER.** La demi-heure de 44 px est la cible de « Placer ». Les heures manquantes se reprennent en
   haut de l'écran (J1).
2. **Case dans les blocs, sauf blocs étroits et colonnes de semaine : GARDER** (gris + icône suffit à distinguer l'ERP).
3. **Planifier en plein écran : GARDER**, avec P4.
4. **Charge projetée : GARDER, mais juste** (P1).
5. **Mois du bureau avec titres : GARDER.**
6. **Férié en Mois seulement : GARDER.**
7. **Message en haut de Planifier : REVENIR**, dans le volet. **Message et durée fusionnés : GARDER**, avec H4.

## Défauts transversaux
- **T1** : l'ordre de l'en-tête diffère (Aujourd'hui : loupe · Copilote · ⋯ ; Agenda : loupe · ⋯ · Copilote). Prendre
  celui d'Aujourd'hui.
- **T2** : le week-end vide occupe pleine largeur sur bureau (S2, M2, P5).
- **T3** : une même idée, plusieurs formes : non travaillé ×3, ligne de jour ×3, tournure de la charge ×3.
- **T4** : le + flottant recouvre du contenu (un bloc, « dim. 29 », une heure). Dans l'Agenda, l'ancrer au bout de la
  barre « À placer ».
- **T5** : en sombre, les fonds chauds (fait, ambre, olive) virent au brun.
- **Fautes commises** : 1 et 11 (légère) ; aucune autre.

## Les 10 corrections qui changeraient le plus le résultat
1. Une charge projetée juste sur chaque jour cible, ambre au-delà de 4 h, une seule tournure (P1).
2. Planifier sur iPhone : sans +, lignes à plat, cibles sur fond de sélection, seule la tâche choisie cerclée (P2, P3).
3. « Placée … · Annuler » dans le volet (P4).
4. La colonne du jour distincte du week-end (S1).
5. Sur bureau, un non travaillé vide fait 64 px ; chevauchements en cascade (S2, M2, P5).
6. La bande « Toute la journée » sur une rangée, sans la ligne de date : environ 5,6 h visibles (J1).
7. Le + ancré dans la barre « À placer » (J2, T4).
8. À venir sur bureau : liste et panneau (V1).
9. Ouverture à l'heure − 30 min ; blocs faits sans fond (J4, J5).
10. Un même en-tête : ordre, segments fixes, étiquette alignée (T1, V2, J3).
