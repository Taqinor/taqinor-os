# Trace — acceptation ACAL2027 (étapes 3 et 4 « un seul moteur »), 25/11/2026

Pile : instrument privé de revue (copie anonymisée de la production), code = `main` après la PR #1554 + lanes de
correctifs `agri-2`, `devis-2`, `calepinage-2`. Compte : Commercial responsable de la copie. Leads d'essai synthétiques.

## Valeurs relues (leads d'essai seulement)

| Geste | Avant | Après | Où c'est lu |
|---|---|---|---|
| Lead résidentiel créé (facture d'hiver 1 200 MAD, Casablanca, GPS) | — | aucune conception rangée (404) tant qu'aucun champ n'est modifié | route de la conception |
| Un champ modifié (facture d'été) | — | version 1 : 5 panneaux sans batterie · 8 avec ; 2,75 · 4,4 kWc ; 4 398 · 7 037 kWh/an ; 7 152 · 10 930 MAD/an | route de la conception |
| Devis automatique | — | 5 · 8 panneaux, 4,4 kWc, 7 036,6 kWh, 65 900 MAD TTC (option avec) — égaux à la conception | devis ; PDF page 1 (regardée) |
| Devis marqué envoyé puis facture d'hiver 1 200 → 1 800 | 5 · 8 panneaux, 65 900 MAD, PDF 4 pages | IDENTIQUE (chiffres, texte du PDF) ; écart nommé : 8 contre 11 panneaux, 7 037 contre 9 675 kWh, « Réviser » possible | devis, PDF, route de la conception |
| Même changement, brouillon automatique INTACT | 5 · 8 panneaux, 65 900 MAD | 7 · 11 panneaux, 6,05 kWc, 9 675,33 kWh, 78 000 MAD ; historique « Mis à jour : panneaux avec 8 / sans 5 → avec 11 / sans 7 » | devis, onglet devis de la fiche (capture) |
| Même changement, brouillon RETOUCHÉ à l'écran (8 → 9) | 9 · 5 panneaux, 69 300 MAD | 9 · 5 panneaux, 69 300 MAD (gardé) ; listé « retouché à la main » ; à la demande : sans 5 → 7, avec 9 gardé, 69 900 MAD, raisons dites | devis, route de la conception, route de mise à jour |
| Lead commercial (facture 6 000 → 9 000) | 35 · 42 panneaux, 152 600 MAD | 56 · 63 panneaux, 215 200 MAD, historique écrit | devis |
| Lead pompage (débit souhaité 20 → 25 m³/h) | 20 panneaux, 96 100 MAD | 23 panneaux, 104 600 MAD, historique écrit | devis |
| Lead en kWh seuls (650 kWh par mois) | — | devis automatique créé : 4 · 8 panneaux, 65 900 MAD | devis |

Pointeur de chaque devis (lu en base de la copie) : le devis envoyé pointe la version 1 dont il est né (la fiche est
en version 2) ; le brouillon intact et le brouillon mis à jour à la demande pointent la version 2 ; le brouillon né de
« Dupliquer » ne pointe rien.

Fiche du lead (capture regardée) : « Note : Conception recalculée : Facture hiver 1 200 → 1 800 MAD » puis « Facture
hiver : 1200.00 → 1800.00 — par » le compte du vendeur.

Durées (une seule file de tâches de fond sur la pile, deux relecteurs en train de démarrer) : nouvelle version 10 à
30 s ; devis automatique 12 à 18 s.

## Écarts

1. Un lead qui vient d'être créé n'a AUCUNE conception rangée tant qu'un de ses champs n'est pas modifié ; le devis
   automatique la calcule alors dans sa requête. Déjà trouvé par la relecture indépendante de l'étape 5 (point
   bloquant B1) : en correction, lane `lane/moteur-e5-fix`.
2. La conception rangée d'un lead sans toit tracé porte `chaines`, `tension_froid`, `ratio_dc_ac` et `payback` VIDES,
   pour le résidentiel comme pour le commercial, même une fois le devis créé — alors que le PDF du même devis imprime
   un retour sur investissement. Transmis à la lane de l'étape 6 (elle range les verdicts que lisent les contrôles).
3. Facture d'été saisie (900) sans la case « Été différent » : la supposition dit « Facture d'été supposée égale à
   celle d'hiver : renseignez « Facture été » » alors qu'elle EST renseignée ; il faut dire de cocher « Été différent ».
4. Un brouillon né de « Dupliquer » ne pointe aucune conception : il ne suit pas, n'est pas listé « à mettre à jour »
   et aucun écran ne dit qu'il est en retard sur la fiche (vu : deux brouillons du même lead, 65 900 et 78 000 MAD).
5. Lead commercial : quand l'heure de début est saisie et que seule l'heure de fin manque, le refus du devis
   automatique nomme encore le champ de l'heure de début.
6. Phrases de « Mettre à jour » pour un brouillon retouché : « La conception 3D porte le devis de 5 à 7 panneaux » et
   « Écart de calepinage non entièrement appliqué » alors qu'aucun calepinage n'existe (seule la facture a changé).
7. La note « Conception recalculée » s'affiche « — par ? » sur la fiche (aucun auteur : dire « automatique »).
8. Onglet devis de la fiche : un brouillon jamais envoyé porte « Jamais ouvert par le client », l'autre « Pas encore
   envoyé au client » — deux libellés pour le même état.
9. La pastille « kWc devisés » de la fiche suit le DERNIER devis (ici le brouillon dupliqué en retard, 4,40 kWc) et non
   la conception (6,05 kWc) : c'est l'objet de l'étape 7 (ACAL2021), noté pour son rejeu.
10. Ligne d'historique du devis : « (Facture hiver modifié(s)) » — accord à écrire en clair.
11. Durcissement (facultatif) : la route d'enregistrement des lignes croit le drapeau « quantité saisie à la main »
    envoyé par l'écran ; un appelant qui l'oublie voit sa quantité recomposée à la relance suivante (rejoué : 9 → 11).

## Non couvert par ce rejeu

- Le lead 1742 de la copie n'a pas été touché (donnée d'un client réel anonymisé) : le « devis envoyé jamais modifié »
  est prouvé sur un devis d'essai envoyé.
- L'écran « La conception a changé — Mettre à jour » n'existe pas encore (étape 7, AGEN12) : la route est prouvée, pas
  l'écran.
- La retouche a été envoyée par la route de l'écran avec le corps de l'écran, pas par un clic dans l'éditeur ; le clic
  est rejoué par le relecteur X4 du tour 3 du test utilisateur.
