# Maquettes de l'Agenda (L3 n°8) — état après le tour 3

8 fichiers `maquettes/agenda-*.html` (une seule source de données, alignée sur SCENARIO.md), `maquettes/ecrans-agenda.css`,
32 captures re-rendues à 06:32, après le `taches.css` du 06:29. Mesure par script (8 fichiers × 4 rendus) : 0 texte
visible sous 4,5:1, 0 cible sous 44 px. Seule exception : les libellés du rail du bureau, mis à 0 px exprès (ils
restent lus par le lecteur d'écran). Aucune couleur littérale.

## Scénario
Mardi 24, 09:41 (« 1 sur 5 » de la tuile). Toute la journée : « Visite technique à Témara » et « Confirmer la
réservation du stand · 30 min ». Les 5 gardées pèsent 4 h 15, ce que dit « 4 h 15 pour 4 h », en ambre. Les durées
sont affichées partout où elles comptent (cartes de Planifier, puces de la Semaine) : mer. 2 h 30 et ven. 2 h 30 se
recomptent. À placer : 10 partout (2 à revoir + 8 dans les projets).

## Tour 3 : corrections (critique tour 2)
- **N1** : le trait « maintenant » passe SOUS les blocs ; seuls le point et « 09:41 » restent dans la gouttière. Le bloc
  fait est opaque, couleur de la surface.
- **N2** : en Planifier, chaque jour montre ses chiffres actuels (« 2 tâches · 2 h pour 4 h »). Quand une tâche est
  choisie, « + 2 h » s'affiche en tête de ligne : en azur s'il reste de la place, en `--tch-surveiller` au-delà de 4 h.
  Sur bureau, la colonne survolée fait de même.
- **N3** : en sombre, le fond de terre, ambre et olive se mélange en sRGB (gris neutre), par surcharge.
- **J1** : ouverture à 08:30, quand un bloc commence dans la demi-heure ; ruban de 50 px ; bande de 46 px. Environ 4,8 h
  visibles : la barre d'état partagée coûte 47 pt.
- **J3** : « Toute la journée » a le bord gauche des heures, sur iPhone et sur bureau.
- **S2** : rail d'icônes de 64 px en Semaine et Mois. Colonnes d'environ 165 px ; chevauchement en cascade à 10 % ; puces
  sur 2 lignes. Plus aucun titre coupé dans les blocs.
- **P5** : nom du projet entier sur les cartes.
- **P6** : le week-end garde le fond du non travaillé ; il reste touchable.
- **Volet** ancré sous les jours, avec une marge pour l'indicateur d'accueil.
- **m1** : les créneaux ont la forme des cibles (fond de sélection, sans +).
- **m2** : « À placer · 10 » partout ; « +4 » comme le Mois.
- **m4** : barre latérale et panneau sur `--background`.
- **m5** : la surcharge se dit aussi en mots ; fantôme opaque.
- **Placer** : la pose est à 12:00, visible avec le titre du devis.

## Écarts assumés
1. 88 px/h (le jeton partagé).
2. Case dans les blocs, sauf blocs étroits et colonnes de semaine.
3. Planifier est un mode : plein écran sur iPhone, sans barre latérale sur bureau.
4. Semaine bureau en cascade ; Jour en côte à côte.
5. Mois bureau avec titres.
6. Férié en Mois seulement.
7. Rail de 64 px en Semaine et Mois, barre latérale entière ailleurs.
8. m3 non tranché : la bande garde les tâches sans heure (spec 3 §3.7). La spec 7 §3 dit « visites et poses » : à aligner
   dans la spec.

## À reporter dans taches.css
- `taches.css:148` : `.dark [data-p="terre"|"ambre"|"olive"]` mélange `in oklch` → `in srgb` (sinon le fond vire au mauve).
- `.maintenant` au z-index 2 passe au-dessus des blocs : le mettre sous les blocs (point et heure dans la gouttière).
- `.bloc.fait-bloc` transparent : le trait « maintenant » le barre ; le mettre sur `--tch-surface`.
- Rail d'icônes de la barre latérale (64 px) à verser dans `.page.trois` pour les vues larges.

## Ce qui déplaît encore
- Jour iPhone à 4,8 h visibles, pas 5,6.
- Les titres passés du Mois bureau se répètent (le réservoir est petit).
- Sur iPhone, les jours repliés d'À venir restent sous la ligne de flottaison.
- Non vérifié sur un vrai iPhone.

**« Toucher puis poser »** : sans la consigne, chaque jour annonce « + 2 h » et dit s'il déborde, et une seule tâche est
cerclée. La consigne reste comme filet.
