# Langage visuel v2 de l'atelier Calepinage (23/11/2026)

Les maquettes v1 (`../maquettes/`) ont fixé l'OSSATURE : un bandeau de projet, un rail de cinq étapes, la carte au
centre, un panneau d'étape court à droite, un seul bouton doré par écran. La v2 garde cette ossature, les mêmes
textes et les mêmes données d'exemple (Villa Bennani — Casablanca), et change la FINITION. Elle ne déplace aucune
fonction : un écran construit sur la v1 passe à la v2 par ses styles et quelques composants, pas par une refonte.

Sources : `../T2/R1-beaute-simplicite.md` (recherche du 22/11/2026). Maquettes de référence de ce langage, écrites en
premier : `Main.dc.html` (étape Toit) et `Resultats.dc.html` (étape Résultats). En cas de doute, on copie ces deux-là.

## Les cinq changements, dans l'ordre de ce qu'on remarque

1. **La carte est le décor.** Sur les étapes Toit, Panneaux et Électrique, la vue aérienne occupe tout l'écran ; le
   bandeau, le rail, le panneau d'étape et les outils flottent dessus (marge de 16 px, coins arrondis, ombre douce,
   léger flou de l'arrière-plan). Sur les étapes sans carte (Résultats, Documents, Liste), le fond est un papier chaud
   `#f5f4f0` et les mêmes pièces flottantes sont blanches et opaques.
2. **Le bleu nuit porte l'état actif, l'or ne sert qu'à l'action suivante.** Étape active du rail, outil actif, bouton
   « Générer le devis », tuile choisie : bleu nuit `#0c1335`. Le seul aplat doré d'un écran est le bouton qui fait
   avancer (« Poser les panneaux », « Préparer les documents »…). L'or revient en trait fin pour ce qui se rapporte au
   soleil ou à la production (contour du toit, barres de production, pastille « supposé »).
3. **Les chiffres sont dessinés.** Archivo, graisse 600 ou 700, crénage serré ; l'unité est plus petite (≈ un tiers),
   en gris, sur la même ligne de base ; chiffres tabulaires partout (`font-variant-numeric: tabular-nums`).
4. **La profondeur vient de la lumière, pas des traits.** Plus de cadre gris autour de chaque bloc : une ombre
   teintée de bleu nuit et des filets à 8-14 % d'opacité. Sur la carte, chaque objet porte l'ombre du soleil affiché.
5. **Ce qui est supposé se voit.** Une pastille dorée de 7 px marque toute valeur publiée ou de départ qui n'a pas été
   mesurée ; la bande « Ce que ce résultat suppose » les réunit sous les résultats.

## Jetons

| Rôle | Clair | Sombre |
|---|---|---|
| Fond de page sans carte | `#f5f4f0` | `#0a0f2a` |
| Surface (cartes, panneau) | `#ffffff` | `#121a3f` |
| Surface 2 (pistes, fonds de champ) | `#ebe9e2` · `#f5f4f0` | `#1a2350` |
| Pièce flottante sur la carte | `rgba(255,255,255,0.86)` à `0.92`, flou 16-18 px, filet `rgba(255,255,255,0.7)` | `rgba(12,19,53,0.82)`, flou 16-18 px, filet `rgba(255,255,255,0.10)` |
| Texte 1 | `#0c1335` | `#f3f5fb` |
| Texte 2 | `#4a5072` | `#a4abcb` |
| Texte 3 (légendes) | `#656b8c` | `#8087a9` |
| Filet | `rgba(12,19,53,0.08)` à `0.14` | `rgba(255,255,255,0.08)` à `0.16` |
| Actif (étape, outil, tuile choisie) | fond `#0c1335`, texte blanc, pictogramme `#e2b54a` | fond `#e2b54a`, texte `#0c1335` |
| Action suivante (un seul par écran) | fond `#e2b54a`, texte `#0c1335`, ombre `0 8px 20px rgba(201,154,43,0.38)` | idem |
| Or en texte ou en trait sur blanc | `#8a6a12` (texte) · `#c99a2b` (trait) | `#e2b54a` |
| Lien | `#1f4fd8` | `#6c86f2` |
| Fait, conforme | `#1e7a57` | `#3dbe8b` |
| À surveiller | fond `#fbf6e6`, filet `#efdfae`, texte `#5b4a12` | fond `rgba(226,181,74,0.14)`, texte `#f0d48a` |
| À régler, refus | `#c2410c` | `#f26b5b` |
| Production | `#e2b54a` (dégradé `#ecc463` → `#dba93a`) | idem |
| Consommation | `#1f4fd8` | `#6c86f2` |
| Perte dans une barre | `#e9a48a` | `#c9785e` |
| Ensoleillement d'un module (du moins au plus) | `#00224e` `#2a3f6d` `#575d6d` `#7d7c78` `#a59c74` `#d2c060` `#fee838` (lisible par les daltoniens) | idem |

- **Polices** : Archivo (titres, chiffres : 600, 700) ; Hanken Grotesk (interface : 400, 500, 600, 700). Aucun texte
  sous 12 px.
- **Échelle** : 12 légendes · 13 étiquettes et texte secondaire · 14 texte · 16 saisies et titres de projet · 18 titres
  de carte · 24 titre d'étape · 38 chiffre de carte · 58 chiffre principal · 64-72 présentation au client.
- **Rayons** : 8-10 champs et puces · 11-12 boutons et tuiles · 14-16 pièces flottantes moyennes · 20-22 panneau,
  rail, cartes de résultat.
- **Ombres** (teintées bleu nuit) : carte posée `0 8px 24px rgba(12,19,53,0.07), 0 1px 2px rgba(12,19,53,0.06)` ;
  pièce flottante sur la carte `0 10px 34px rgba(12,19,53,0.16), 0 1px 3px rgba(12,19,53,0.08)` ; panneau d'étape
  `0 18px 48px rgba(12,19,53,0.22)`.
- **Mesures de la coque** : marge 16 · bandeau 56 de haut · rail 76 de large, tuiles 60 × 64 · panneau d'étape 384 de
  large · barre d'outils 56 de haut, boutons 44 × 44 · bouton d'action 52 de haut · cibles tactiles ≥ 44.
- **Mouvement** (pour la construction, invisible sur une maquette fixe) : 120 ms survol et bascule · 220 ms panneaux et
  bulles · 320 ms changement d'étape et apparition des chiffres ; entrée `cubic-bezier(0.05, 0.7, 0.1, 1)`, sortie
  `cubic-bezier(0.3, 0, 0.8, 0.15)` ; `prefers-reduced-motion` : fondu de 80 ms.

## Pièces communes (à recopier telles quelles de `Main.dc.html`)

Bandeau du projet · rail (étape active en tuile bleu nuit, étape faite avec pastille verte cochée, cf.
`Resultats.dc.html`) · panneau d'étape (cinq traits de progression, « Étape n sur 5 », titre, sections, pied avec le
bouton doré) · bulle de consigne bleu nuit · pilule de chiffres vivants · zoom et boussole · barre d'outils · bouton
« Soleil » · cote posée sur un bord · carte « à confirmer ».

## Ce qui ne change pas

Les textes, l'ordre des étapes, le nombre de commandes, les données d'exemple, la règle « rien d'inventé : un bloc dont
la donnée n'existe pas dit qu'il manque ». Les chiffres d'une maquette sont des exemples.
