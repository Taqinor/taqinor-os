# Contrat de hooks DOM `data-ao-*` (AOF8)

> **FIGÉ AVANT le premier écran.** Le dépôt a déjà payé la dérive de ses hooks
> e2e ailleurs (`ap-*`/`att-*`/`pp-*`) : un hook renommé casse des specs
> écrites des semaines plus tôt. Cette liste est normative et a été publiée
> AVANT qu'aucun écran AO n'existe — chaque écran du Groupe AOF **consomme ces
> noms tels quels**, il n'en invente aucun en douce. Ce fichier a **un seul
> propriétaire** dans tout le Groupe AOF (AOF8) : aucune autre tâche ne le
> déclare dans ses `Files:` — le modifier ailleurs unirait deux lanes par
> erreur (`plan_lanes.py` unionne les lanes qui partagent un `Files:`).
>
> Gardé vert par `e2eHooks.test.mjs` (même dossier) : la liste ci-dessous ne
> perd jamais un hook sans que le test le remarque, et aucun écran AO ne peut
> introduire un `data-ao-*` hors de cette liste sans que le test le remarque
> aussi.
>
> **Le contrat s'étend ICI D'ABORD, jamais dans un composant.** Voir la
> « Règle de non-invention » en fin de fichier : toute nouvelle ligne de ce
> document doit être ajoutée **dans le même commit** à `ALL_HOOKS` de
> `e2eHooks.test.mjs`, et l'inverse aussi — le test compare les deux listes et
> refuse la moindre divergence.

## 1. Socle commun (AOF8) — 11 hooks transverses

Ces onze noms sont **prioritaires** : un écran qui a besoin d'un repère
générique (surface de dessin, verdict, compteur, état, provenance…) prend le
nom du socle plutôt que d'en dériver un à lui.

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-canvas` | Le canvas géométrique partagé (toiture from-scratch AOF84, atelier de calepinage AOF92/`StudioShell` AOF73, enveloppes AOF91) | La surface de dessin/rendu SVG ou canvas elle-même — un seul repère par écran, jamais un par outil. |
| `data-ao-outil` | Barre d'outils de tracé/dessin (tracé toiture AOF84, outils obstacles AOF88) | Un bouton d'outil de dessin actif/inactif (tracé, rectangle, polygone, muret…). |
| `data-ao-verdict` | Barre de verdict permanente (AOF93), garde de publication (AOF90) | Le bandeau TOUJOURS visible (compte de modules, kWc, marge signée, statut CONFIRMÉ/TENDU, publiable/bloqué). |
| `data-ao-compte` | Compteur de provenance (AOF90 — « 28 obstacles — 26 mesurés… »), compte de modules (AOF93) | Un chiffre agrégé affiché en continu, jamais un chiffre recalculé côté front (AOF94). |
| `data-ao-tiroir` | Tiroirs de paramètres de l'atelier (Kits AOF95, Allées AOF96, Rives & dégagements AOF97, Orientation & segments AOF98, Contraintes électriques AOF99) | Un panneau de réglage ouvrable/fermable avec impact chiffré. |
| `data-ao-variante` | Sélecteur/carte de variante (atelier variantes — retenue/alternative/sensibilité) | Une variante d'étude individuelle (brouillon/calculé/publiable/périmé — voir `statusAo.js`, AOF10). |
| `data-ao-piece` | Écran « Dossier de soumission » (AOF174), prévisualisation de pièce (AOF175) | Une pièce produite du dossier (à produire/généré/à jour/PÉRIMÉ/fourni/signé/hors contrôle). |
| `data-ao-controle` | Panneau « Contrôles avant dépôt » (AOF176) | Un contrôle individuel de la porte de cohérence croisée (OK/avertissement/bloquant). |
| `data-ao-repere` | Inspecteur d'obstacles (AOF88 — repères lettrés A, B, C…), liste d'obstacles (AOF90) | Le repère lettré d'un obstacle/muret sur le canvas ET dans la liste latérale synchronisée. |
| `data-ao-provenance` | `ProvenanceBadge` (AOF9) | Le badge de provenance d'une valeur (mesuré / à confirmer / déduit / deviné). |
| `data-ao-etat` | Pastilles d'état (`statusAo.js`, AOF10) | La pastille d'état d'une affaire / pièce / variante / contrôle. |

## 2. Atelier de toiture (AOF78 → AOF91) — extension délibérée du contrat

**Pourquoi cette section existe.** Le socle a été figé avant le premier écran,
donc avant que le détail de l'atelier de toiture ne soit connu. Les écrans
livrés (portes d'entrée, underlay, calibration, tracé, cotes, fermetures,
obstacles, zones, enveloppes) ont besoin de repères **par entité et par
action** que onze noms génériques ne peuvent pas porter : `data-ao-canvas` sait
désigner « la surface de dessin », il ne sait pas désigner « le résidu en % de
la chaîne 3 » ni « le bouton qui compense au prorata ». Les lignes ci-dessous
sont donc une **extension assumée du contrat**, pas un contournement de la
garde : chacune correspond à un hook réellement présent dans le code, et à
partir d'ici elles sont figées au même titre que le socle.

**Convention de nommage** — `data-ao-<domaine>` pour le conteneur d'un panneau,
`data-ao-<domaine>-<précision>` pour une entité ou une action à l'intérieur.
Le pluriel désigne le collectif (`data-ao-zones` = le panneau et son compte),
le singulier une occurrence (`data-ao-zone` = une zone).

### 2.1 Wizard « Nouvelle toiture » — AOF78 (`toiture/NouvelleToitureWizard.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-porte` | Wizard « Nouvelle toiture » (AOF78) | Le bouton d'une des trois portes d'entrée CUMULABLES, valué par sa clé (importer un plan / tracer from scratch / reprendre depuis la carte). |
| `data-ao-porte-panneau` | Wizard « Nouvelle toiture » (AOF78) | Le panneau déplié de la porte sélectionnée, valué par la même clé que sa porte. |
| `data-ao-toiture-wizard` | Wizard « Nouvelle toiture » (AOF78) | Le corps du wizard — le point de création UNIQUE d'une toiture. |
| `data-ao-wizard-creer` | Wizard « Nouvelle toiture » (AOF78) | Le bouton qui crée la toiture et ouvre l'éditeur unique, quelle que soit la porte empruntée. |

### 2.2 Calque de fond (underlay) — AOF79 (`toiture/UnderlayPdf.jsx`, `toiture/UnderlayImage.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-underlay` | Underlay PDF et image (AOF79) | Le conteneur du calque de fond, valué par sa source (`pdf` ou `image`). |
| `data-ao-underlay-erreur` | Underlay PDF et image (AOF79) | Le message `role="alert"` de dégradation propre (format non supporté, rasterisation impossible) — jamais une page blanche. |
| `data-ao-underlay-rotation` | Underlay PDF et image (AOF79) | Le bouton de rotation 90° du calque de fond. |

### 2.3 Calibration 2 points — AOF80 (`toiture/Calibration.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-calibration` | Calibration 2 points (AOF80) | La section de calibration entière — bloquante tant que l'échelle est inconnue. |
| `data-ao-calibration-alerte` | Calibration 2 points (AOF80) | L'alerte `role="alert"` de vraisemblance quand l'échelle validée est aberrante. |
| `data-ao-calibration-motif` | Calibration 2 points (AOF80) | Le motif `role="alert"` de refus de la calibration saisie. |
| `data-ao-calibration-surface` | Calibration 2 points (AOF80) | La couche qui capte les deux clics de calibration, au-dessus de l'underlay. |
| `data-ao-calibration-valider` | Calibration 2 points (AOF80) | Le bouton qui fixe le facteur px→m. |
| `data-ao-echelle` | Calibration 2 points (AOF80) | L'en-tête d'état de l'échelle — porte « échelle inconnue » et l'avertissement de désactivation du tracé et de la cotation. |

### 2.4 Import DXF — AOF81 (`toiture/ImportDxf.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-dxf-apercu` | Import DXF (AOF81) | L'aperçu SVG auto-recentré du calque d'enveloppe choisi. |
| `data-ao-dxf-calques` | Import DXF (AOF81) | Le tableau de mapping des calques et de leur nombre d'entités. |
| `data-ao-dxf-degrade` | Import DXF (AOF81) | Le bloc `role="alert"` d'état dégradé quand l'endpoint de parsing est absent ou en erreur. |
| `data-ao-dxf-importer` | Import DXF (AOF81) | Le bouton qui valide le mapping et importe l'enveloppe et les obstacles. |
| `data-ao-dxf-repli` | Import DXF (AOF81) | Le repli explicite vers le tracé à la main depuis l'état dégradé. |
| `data-ao-import-dxf` | Import DXF (AOF81) | L'écran d'import DXF entier. |

### 2.5 Reprise depuis la carte — AOF82 (`toiture/RepriseCarte.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-carte-repli` | Reprise depuis la carte (AOF82) | Le repli vers le tracé à la main quand le montage du lecteur de cartes casse. |
| `data-ao-carte-reprendre` | Reprise depuis la carte (AOF82) | Le bouton qui reprend le contour tracé sur la carte et le convertit en enveloppe locale. |
| `data-ao-reprise-carte` | Reprise depuis la carte (AOF82) | Le panneau de capture cartographique, valué par son état (dont `degrade` — l'atelier ne s'écroule jamais). |

### 2.6 Outil de tracé from scratch — AOF84 (`toiture/OutilTrace.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-outil-trace` | Outil de tracé (AOF84) | Le panneau de tracé souris ET clavier. |
| `data-ao-trace-annuler` | Outil de tracé (AOF84) | Le bouton d'annulation de la dernière étape (undo par étape). |
| `data-ao-trace-direction` | Outil de tracé (AOF84) | Un bouton de direction orthogonale, valué par son angle en degrés. |
| `data-ao-trace-erreur` | Outil de tracé (AOF84) | Le message `role="alert"` de refus (auto-intersection, longueur invalide). |
| `data-ao-trace-etat` | Outil de tracé (AOF84) | La ligne d'état du contour — nombre de sommets, ouvert/fermé, aire et périmètre une fois fermé. |
| `data-ao-trace-fermer` | Outil de tracé (AOF84) | Le bouton de fermeture automatique du contour. |
| `data-ao-trace-sommets` | Outil de tracé (AOF84) | La liste des sommets saisis, valuée par leur nombre. |

### 2.7 Chaînes de cotes — AOF85 (`toiture/ChainesCotes.jsx`, `toiture/Cote.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-chaine` | Chaînes de cotes (AOF85) | Le groupe SVG d'UNE chaîne sur la planche, valué par son identifiant. |
| `data-ao-chaine-axe` | Chaînes de cotes (AOF85) | L'axe de la chaîne rendue (`x` ou `y`). |
| `data-ao-chaine-edition` | Chaînes de cotes (AOF85) | Le `fieldset` d'édition inline d'une chaîne, valué par son identifiant. |
| `data-ao-chaine-nouvelle` | Chaînes de cotes (AOF85) | Le bouton de création d'une chaîne sur l'axe donné en valeur. |
| `data-ao-chaine-somme` | Chaînes de cotes (AOF85) | La somme calculée des segments d'une chaîne, valuée par l'identifiant de la chaîne. |
| `data-ao-chaines` | Chaînes de cotes (AOF85) | Le panneau des chaînes, valué par leur nombre. |
| `data-ao-chaines-planche` | Chaînes de cotes (AOF85) | La planche SVG de rendu type plan des chaînes (lignes d'attache, double flèche, texte orienté). |
| `data-ao-cote` | Cote rendue type plan (AOF85) | Une cote individuelle rendue sur la planche. |
| `data-ao-cote-axe` | Cote rendue type plan (AOF85) | L'axe de la cote rendue. |
| `data-ao-cote-provenance` | Cote rendue type plan (AOF85) | La provenance qui pilote la COULEUR de la cote (voir AOF9) — c'est elle qui bascule en « à confirmer ». |
| `data-ao-cote-texte` | Cote rendue type plan (AOF85) | Le texte orienté de la cote, lisible à tous les zooms. |

### 2.8 Fermetures et arbitrage — AOF86 (`toiture/FermeturesPanel.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-arbitrage` | Panneau « Fermetures » (AOF86) | Le bloc d'arbitrage OBLIGATOIRE d'une chaîne en écart, valué par son identifiant. |
| `data-ao-fermeture` | Panneau « Fermetures » (AOF86) | La ligne de fermeture d'UNE chaîne, valuée par son identifiant. |
| `data-ao-fermeture-accepter` | Panneau « Fermetures » (AOF86) | L'acceptation explicite d'un écart, qui exige un motif écrit et persisté. |
| `data-ao-fermeture-apercu` | Panneau « Fermetures » (AOF86) | L'aperçu AVANT/APRÈS de la compensation au prorata. |
| `data-ao-fermeture-appliquer` | Panneau « Fermetures » (AOF86) | Le bouton qui applique effectivement la compensation au prorata (spread). |
| `data-ao-fermeture-motif` | Panneau « Fermetures » (AOF86) | Le motif d'acceptation persisté et affiché, valué par l'identifiant de la chaîne. |
| `data-ao-fermeture-prorata` | Panneau « Fermetures » (AOF86) | Le bouton qui propose la compensation au prorata d'une chaîne. |
| `data-ao-fermeture-residu` | Panneau « Fermetures » (AOF86) | Le résidu de fermeture en mètres. |
| `data-ao-fermeture-residu-pct` | Panneau « Fermetures » (AOF86) | Le résidu de fermeture en pourcentage. |
| `data-ao-fermeture-statut` | Panneau « Fermetures » (AOF86) | Le statut OK/ÉCART de la chaîne, au comportement de `solveur.py:closure`. |
| `data-ao-fermetures` | Panneau « Fermetures » (AOF86) | Le panneau des fermetures entier. |
| `data-ao-fermetures-calepiner` | Panneau « Fermetures » (AOF86) | Le passage au calepinage — désactivé tant qu'une chaîne est en écart non arbitré. |
| `data-ao-fermetures-verrou` | Panneau « Fermetures » (AOF86) | Le message `role="alert"` du verrou métier qui interdit ce passage. |

### 2.9 Points à lever — AOF87 (`toiture/PointsALever.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-point` | Section « à lever au relevé d'exécution » (AOF87) | Un point à lever, valué par son identifiant. |
| `data-ao-point-motif` | Section « à lever au relevé d'exécution » (AOF87) | Le motif d'entrée automatique du point dans la section (déduction, écart avec la valeur annoncée). |
| `data-ao-point-provenance` | Section « à lever au relevé d'exécution » (AOF87) | La provenance du point — une cote déduite ne peut jamais rester en « mesuré ». |
| `data-ao-points-lever` | Section « à lever au relevé d'exécution » (AOF87) | La section entière, valuée par le nombre de points. |
| `data-ao-points-lever-export` | Section « à lever au relevé d'exécution » (AOF87) | L'export de la liste des points à lever. |
| `data-ao-points-lever-invariant` | Section « à lever au relevé d'exécution » (AOF87) | L'alerte `role="alert"` quand l'invariant est violé (une cote déduite absente de la liste). |
| `data-ao-points-lever-vide` | Section « à lever au relevé d'exécution » (AOF87) | L'état vide de la section. |

### 2.10 Obstacles : outils et inspecteur — AOF88 (`toiture/OutilsObstacles.jsx`, `toiture/ObstacleInspecteur.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-inspecteur` | Inspecteur d'obstacle (AOF88) | Le panneau d'inspection, valué par le repère lettré inspecté ou `vide`. |
| `data-ao-obstacle` | Outils obstacles (AOF88) | L'emprise dessinée d'un obstacle sur la planche, valuée par son repère lettré. |
| `data-ao-obstacle-brouillon` | Outils obstacles (AOF88) | Le polygone en cours de saisie, valué par son nombre de points. |
| `data-ao-obstacle-degagement` | Inspecteur d'obstacle (AOF88) | Le dégagement AUTO-DÉRIVÉ de la provenance (0,30 / 0,50), valué par le repère. |
| `data-ao-obstacle-halo` | Outils obstacles (AOF88) | Le halo translucide de dégagement rendu autour de l'emprise, valué par sa distance. |
| `data-ao-obstacle-nature` | Outils obstacles (AOF88) | La nature de l'obstacle parmi les 13 types, qui pilote son rendu distinct. |
| `data-ao-obstacle-rendre-derive` | Inspecteur d'obstacle (AOF88) | Le retour à la valeur auto-dérivée après une surcharge manuelle. |
| `data-ao-obstacle-surcharge` | Inspecteur d'obstacle et outils obstacles (AOF88) | Le badge « surchargé » — le dégagement ne vient plus de la provenance mais d'une saisie. |
| `data-ao-obstacles-doublons` | Outils obstacles (AOF88) | L'alerte `role="alert"` de repères en collision. |
| `data-ao-obstacles-planche` | Outils obstacles (AOF88) | La planche SVG de pose des obstacles. |
| `data-ao-outil-terminer` | Outils obstacles (AOF88) | La fermeture du polygone d'obstacle en cours. |
| `data-ao-outils-obstacles` | Outils obstacles (AOF88) | Le panneau des outils obstacles, valué par le nombre d'obstacles. |

### 2.11 Zones (interdite / réservée / préférée) — AOF89 (`toiture/OutilsZones.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-zone` | Outil de saisie des zones (AOF89) | Le polygone dessiné d'UNE zone, valué par son identifiant. |
| `data-ao-zone-ajouter-point` | Outil de saisie des zones (AOF89) | L'ajout d'un point saisi au clavier au polygone en cours. |
| `data-ao-zone-brouillon` | Outil de saisie des zones (AOF89) | Le polygone de zone en cours de saisie, valué par son nombre de points. |
| `data-ao-zone-erreur` | Outil de saisie des zones (AOF89) | Le message `role="alert"` de refus de la zone saisie. |
| `data-ao-zone-legende` | Outil de saisie des zones (AOF89) | Une entrée de légende, valuée par la clé de nature qu'elle explique. |
| `data-ao-zone-ligne` | Outil de saisie des zones (AOF89) | La ligne de tableau récapitulant une zone. |
| `data-ao-zone-nature` | Outil de saisie des zones (AOF89) | La nature d'une zone (interdite / réservée / préférée), qui pilote son rendu distinct. |
| `data-ao-zone-outil` | Outil de saisie des zones (AOF89) | Le bouton de choix de nature avant tracé, valué par sa clé. |
| `data-ao-zone-terminer` | Outil de saisie des zones (AOF89) | La fermeture du polygone de zone en cours. |
| `data-ao-zones` | Outil de saisie des zones (AOF89) | Le panneau des zones, valué par leur nombre. |
| `data-ao-zones-compte` | Outil de saisie des zones (AOF89) | Le compte de modules RENVOYÉ PAR LE SERVEUR, comparé à l'écran pour prouver qu'une zone préférée ne change jamais le compte. |
| `data-ao-zones-legende` | Outil de saisie des zones (AOF89) | La légende générée depuis les seules natures réellement présentes, valuée par leur nombre. |
| `data-ao-zones-planche` | Outil de saisie des zones (AOF89) | La planche SVG de pose des zones. |
| `data-ao-zones-regle` | Outil de saisie des zones (AOF89) | La règle affichée en permanence — une zone préférée ne change JAMAIS le compte, elle ne sert qu'au départage. |
| `data-ao-zones-surface-retiree` | Outil de saisie des zones (AOF89) | La surface retirée par les zones interdites et réservées, en m². |

### 2.12 Liste d'obstacles et garde de publication — AOF90 (`toiture/ObstaclesList.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-fautif` | Liste d'obstacles (AOF90) | Marque l'obstacle NOMMÉ par la garde comme bloquant la publication. |
| `data-ao-obstacles` | Liste d'obstacles (AOF90) | La liste latérale synchronisée, valuée par le total d'obstacles. |
| `data-ao-obstacles-vide` | Liste d'obstacles (AOF90) | L'état vide après filtrage. |
| `data-ao-poser-question` | Liste d'obstacles (AOF90) | L'action « poser la question au client », valuée par les repères concernés — crée directement une question Q/R. |
| `data-ao-survole` | Liste d'obstacles (AOF90) | La synchronisation survol ↔ surbrillance entre la liste et le canvas. |

### 2.13 Enveloppes non rectangulaires — AOF91 (`toiture/EnveloppeL.jsx`, `toiture/EnveloppeArc.jsx`)

| Hook | Propriétaire (écran / tâche) | Sémantique |
|---|---|---|
| `data-ao-arc-a-cheval` | Enveloppe en arc (AOF91) | Le nombre de rangées proposées à cheval sur un muret — doit rester à zéro. |
| `data-ao-arc-developpe` | Enveloppe en arc (AOF91) | Le développé total de l'arc en mètres. |
| `data-ao-arc-muret` | Enveloppe en arc (AOF91) | Un muret (joint) rendu sur le développé, valué par son index. |
| `data-ao-arc-muret-reel` | Enveloppe en arc (AOF91) | Le même muret rendu sur la vue réelle. |
| `data-ao-arc-pas` | Enveloppe en arc (AOF91) | Le pas angulaire calculé de l'arc. |
| `data-ao-arc-refus` | Enveloppe en arc (AOF91) | La liste `role="alert"` des motifs de refus (arc sans rayon ni largeur), valuée par leur nombre. |
| `data-ao-arc-rendu` | Enveloppe en arc (AOF91) | Un des deux rendus côte à côte, valué par sa vue (`developpe` ou `reel`). |
| `data-ao-arc-segment` | Enveloppe en arc (AOF91) | Un segment rendu sur le développé, valué par son index. |
| `data-ao-arc-segment-reel` | Enveloppe en arc (AOF91) | Le même segment rendu sur la vue réelle. |
| `data-ao-arc-valider` | Enveloppe en arc (AOF91) | Le bouton de validation de l'enveloppe en arc. |
| `data-ao-enveloppe` | Enveloppes non rectangulaires (AOF91) | Le panneau de saisie d'une enveloppe, valué par sa forme (`l` ou `arc`). |
| `data-ao-l-aire` | Enveloppe en L (AOF91) | La surface d'enveloppe du contour en m². |
| `data-ao-l-bande` | Enveloppe en L (AOF91) | La bande traversante rendue sur le canvas — celle que le découpage en deux rectangles couperait. |
| `data-ao-l-bande-traversante` | Enveloppe en L (AOF91) | La hauteur en mètres de cette bande sous l'aile. |
| `data-ao-l-incomplet` | Enveloppe en L (AOF91) | L'invite à compléter la barre et l'aile avant validation. |
| `data-ao-l-perte` | Enveloppe en L (AOF91) | La perte sèche en modules qu'entraînerait le découpage en deux rectangles. |
| `data-ao-l-refus` | Enveloppe en L (AOF91) | La liste `role="alert"` des motifs de refus, valuée par leur nombre. |
| `data-ao-l-regle` | Enveloppe en L (AOF91) | La règle affichée en permanence — le L se saisit comme UNE surface continue, jamais deux rectangles. |
| `data-ao-l-sommets` | Enveloppe en L (AOF91) | Le polygone UNIQUE du contour, valué par son nombre de sommets. |
| `data-ao-l-valider` | Enveloppe en L (AOF91) | Le bouton de validation de l'enveloppe en L. |

### 2.14 Fiche affaire : panneaux d'onglet en chargement différé — 03/08/2026 (`AffaireDetail.jsx`)

| Hook | Porté par | Sémantique |
|---|---|---|
| `data-ao-panneau-differe` | Le repli squelette de `PanneauDiffere` | Le panneau de cet onglet est en cours de chargement (`lazy` + `Suspense`). Repère destiné au balayage e2e : un onglet doit finir par REMPLACER ce repère par son contenu réel — s'il persiste, le panneau ne se monte pas. |

## Règle de non-invention

Un écran AO qui a besoin d'un hook e2e stable choisit **d'abord un nom du
socle** (§1). Si un besoin réel ne correspond à AUCUN nom déjà publié, la liste
s'étend **ici d'abord** — nouvelle ligne dans la section de l'écran concerné
(ou nouvelle section si c'est un écran nouveau) **et** mise à jour d'`ALL_HOOKS`
dans `e2eHooks.test.mjs`, **dans le même commit** — jamais en douce dans un
composant.

Un hook retiré du code se retire des deux listes en même temps ; un hook
renommé est un hook retiré plus un hook ajouté. Le test refuse toute
divergence entre ce document, `ALL_HOOKS` et le code de `features/ao/**`, dans
les deux sens.
| `data-ao-annotation-serie` | Annotateur de la série de questions (`SeriesPage`, PACT170) | Le repère posé sur l'image annotée — un par marqueur, portant sa lettre. |
| `data-ao-note-question` | Fiche question ouverte depuis un repère (`SeriesPage`, PACT170) | La saisie de la question rattachée à UN repère (texte + impact chiffré). |
| `data-ao-legende-provenance` | Bandeau de provenance de l'atelier toiture (`ToituresPage`, PACT166) | La légende qui NOMME d'où vient chaque cote (relevée, lue sur plan, devinée). |
| `data-ao-enveloppe-arc-retenue` | Outil enveloppe en arc (`ToituresPage`, PACT167) | L'enveloppe arc RETENUE, une fois publiée dans le contour de l'atelier. |
| `data-ao-question-proposee` | Atelier toiture (`ToituresPage`, PACT167) | Une question terrain PROPOSÉE par l'atelier, pas encore créée côté serveur. |
| `data-ao-atelier-note` | Atelier toiture (`ToituresPage`, PACT166/167) | Une limite ÉCRITE de l'atelier (ce qu'il ne sait pas faire), jamais un bouton mort. |
| `data-ao-impose` | Studio de calepinage, mode plan imposé (`CalepinageStudio`, PV31) | La barre d'outils du mode « rangées imposées » (annuler/rétablir/supprimer/revenir). |
| `data-ao-impose-verdict` | Barre de verdict en mode imposé (`VerdictBar`, PV32) | Le bandeau « Plan imposé — non optimal » quand la preuve est `impose_utilisateur`. |
| `data-ao-ecart-optimum` | Barre de verdict en mode imposé (`VerdictBar`, PV32) | Le badge d'écart honnête (« -N modules vs optimum ») lu VERBATIM du serveur. |
| `data-ao-variante-retenue` | Liste des calepinages (`VariantesListPage`, PV59) | L'étoile de la variante RETENUE d'une toiture dans la liste transverse. |
| `data-ao-raisons-non-publiabilite` | Liste des calepinages (`VariantesListPage`, PV59) | Le dépliant des raisons de non-publiabilité servies par la garde serveur. |
| `data-ao-synthese-calepinage` | Onglet Calepinages de l'affaire (`AffaireDetail`, PV68/PV59) | Le bloc « Synthèse » multi-toitures (Σ modules/kWc des variantes retenues). |
| `data-ao-synthese-toitures` | Onglet Calepinages de l'affaire (`AffaireDetail`, PV68/PV59) | La ligne par toiture de la synthèse (calepinée ou non, jamais masquée). |
