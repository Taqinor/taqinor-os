# Cerveau V3 de l'estimateur — méthode (preview privé `/preview/toiture-3d-pro-6`)

Ce fichier documente la **méthode** du cerveau V3 (`src/lib/estimatorBrainV3.ts`),
branché sur la page privée `/preview/toiture-3d-pro-6` via `src/scripts/roof-tool-pro6.ts`.
Aucune donnée client n'est committée — uniquement la logique. Jamais un devis : une
fourchette indicative. V3 **compose** sur V2 (`estimatorBrainV2.ts`) **sans le modifier** :
pro-3/pro-4/pro-5 restent des baselines intactes.

## Ce que V3 ajoute (et ce qu'il ne touche pas)

V3 n'ajoute que trois choses, toutes **additives** :

1. **Recherche pleine de l'optimum** (`fullSearchOptimum`). La recommandation
   « Optimum » est calculée sur tout le **produit cartésien** d'axes — famille
   (Sud / Est-Ouest) × inclinaison (balayage **fin** 5°→optimal, pas 1°) × azimut
   (plein sud / aligné sur les arêtes) × calepinage (portrait / paysage) × marge de
   rive (garder / retirer) — chaque configuration **plafonnée au besoin** dicté par
   la facture, scorée sur l'**énergie POSÉE** (qui encode l'adéquation au besoin
   puisque tout est capé). Le vrai gagnant peut donc utiliser une combinaison
   (ex. marge retirée + paysage) que le tableau visible ne montre pas. L'**espace de
   recherche** (riche) est **découplé du tableau affiché** (qui reste court).
   Garantie de non-régression testée : l'optimum V3 n'est **jamais pire** que la reco
   V2 sur l'énergie posée.

2. **Ré-optimisation contrainte** (`reoptimize`). Le bouton « Optimum » lit les axes
   que l'utilisateur a **épinglés** (cliqué une option). Sans épingle → optimum
   global. Avec une épingle (ex. inclinaison 15°, ou Est-Ouest forcé) → on **tient**
   cet axe et on **re-résout tous les autres** au mieux sous cette contrainte. Le
   badge « Recommandé » de chaque groupe reste celui de l'optimum **global** (sans
   épingle), donc l'utilisateur voit toujours « j'ai choisi X mais Y est recommandé ».

3. **Modèle toit en pente / tuiles** (`packFlushPlane`, `recommendPitched`). Un
   **second** modèle de toit : panneaux posés **affleurants** sur la pente.

## Physique du toit en pente (pose affleurante)

- **La pente ne se mesure PAS sur l'imagerie marocaine.** Satellite top-down
  uniquement ; pas de vols aériens ni de Street View exploitable. Aurora / Project
  Sunroof s'appuient sur du **LiDAR + photogrammétrie aérienne HD** et, à défaut,
  retombent sur un **tracé manuel + pente saisie**. La pente est donc **SAISIE** par
  l'utilisateur (presets ~15° / ~22° / ~30°, réglables), jamais devinée.
- **Inclinaison de l'array = pente du toit. Azimut de l'array = face du pan.** Tous
  deux **imposés par la toiture**, affichés en lecture seule (« imposé par la
  toiture »), **jamais choisis ni balayés** par l'optimiseur.
- **Pas d'auto-ombrage entre panneaux coplanaires d'un même pan ⇒ AUCUN pas de
  rangée solaire.** Tuile bord à bord, moins un petit jeu de maintenance / accès
  incendie (`FLUSH_MAINTENANCE_GAP_M = 0,15 m`, en plan). C'est ce qui fait qu'un
  toit en pente loge **bien plus** de panneaux qu'un toit plat de même surface (le
  toit plat réserve l'ombre inter-rangées au solstice). Le pas de rangée affleurant
  en plan = empreinte plan (`longueur·cos(pente) × largeur`) + le jeu, **jamais** le
  pas de rangée du toit plat.
- **Production par pan via PVGIS à la pente + l'azimut RÉELS** (table committée par
  latitude, déjà dans la stack — pas une nouvelle dépendance). Le rendement par
  panneau baisse honnêtement quand la face s'écarte du sud.
- **Multi-pans** (`recommendPitched` accepte N pans) : on classe les pans par
  rendement/panneau, on **saute/signale** un pan orienté nord
  (`NORTH_FACING_OFFSOUTH_DEG = 90°` au-delà du sud), et on remplit du meilleur au
  moins bon **jusqu'au besoin** (plafond partagé), jamais au-delà.

## Règles partagées (identiques au toit plat / V2)

- **Plafond « besoin ».** Posés = `min(besoin, ce qui tient)`. Aucun sur-remplissage
  d'un toit spacieux (le surplus est non rémunéré au Maroc — pas de net-billing BT
  clair).
- **Plafond économies.** Économies ≤ coût énergie évitable (barème régie ONEE
  sélectif, TTC). Surplus au-delà de la conso = 0.
- **Bornes physiques.** Σ empreintes au sol ≤ surface utile ; chaque empreinte
  entièrement dans le tracé ; obstacles (+ dégagement) retirés.

## Garantie « chemin toit plat inchangé »

Le mode **Toit plat** de pro-6 **réutilise la physique de V2 sans la forker** :
`evalFlatConfig` appelle `packConfig` + `productionKwh` de V2 (prouvé par test : même
pavage, même production), et le mode plat de l'écran appelle **le même
`recommend(ring, centroidLat, bill, obstructionRings(), { setbackM, enableRoofAligned: true })`**
que pro-5. Le rendu 3D ajoute un paramètre `flush` qui **vaut `false` par défaut** :
le rendu toit-plat est donc octet pour octet celui de pro-5. La recherche pleine et
le bouton « Optimum » sont une **couche au-dessus**, déclenchée par une action
explicite de l'utilisateur.

## Honnêteté de vérification (ce que seul le téléphone confirme)

L'agent de build **ne peut pas** rendre la carte interactive en local (les clés
MapTiler/Mapbox vivent dans Cloudflare). Tout ce qui est **géométrique/numérique** est
donc verrouillé par des **invariants testés** (`tests/estimatorBrainV3.test.ts`,
22 cas) :

- pente == inclinaison et face == azimut en mode pente (imposés, non balayés) ;
- pas de rangée affleurant = empreinte plan + jeu (zéro ombre solaire) ;
- pose affleurante loge **strictement plus** qu'un toit plat de même surface/pente ;
- Σ empreintes ≤ surface utile ; pan nord sauté/signalé ; plafonds besoin/économies ;
- optimum = vrai gagnant du produit cartésien, jamais pire que la reco V2 ;
- épingle tenue par `reoptimize`, badges = optimum global.

Ce que **seul l'œil sur la carte (téléphone du fondateur)** peut confirmer : le rendu
3D affleurant (panneaux couchés sur la pente, sans châssis ni lest — rendu
**schématique** : le bâtiment garde un volume plat, seuls les panneaux portent
l'inclinaison du toit), l'alignement de la photo satellite, et l'ergonomie tactile.
