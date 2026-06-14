# Notes — estimateur 3D haute fidélité (`/preview/toiture-3d-pro-2`)

Upgrade physique + visuel de la version « racks » (`/preview/toiture-3d-pro`). Quatre
améliorations, toutes ajustables dans `src/lib/roofPro2.ts` et `src/scripts/roof-tool-pro2.ts`.

## 1. Vrai panneau : Canadian Solar TOPBiHiKu7 CS7N-690-720TB-AG
- Dimensions **2384 × 1303 × 33 mm**, **720 Wc**, bifacial double-verre, **132 demi-cellules**.
- Monté **paysage** (grand côté 2,384 m le long de la rangée).
- Rendu : verre **tout noir** (pas de busbars apparents), grille demi-cellules + **couture
  centrale** en texture (pas en géométrie → peu de polygones), cadre alu fin, **boîtier de
  jonction** au dos, verre **brillant** (clearcoat). `kWc = nombre × 0,72`.

## 2. Vrai sud, géo-ancré
- L'orientation choisie fixe un **azimut RÉEL** (Sud=180°, SE=135°, SO=225°, E=90°, O=270°,
  N=0°). La scène vit dans l'espace géographique (ENU → mercator) : quand on **tourne la
  carte**, les panneaux gardent leur cap réel — pas le « sud de l'écran ».
- **Boussole** en haut à gauche : l'aiguille N/S pivote avec le cap.

## 3. Vrai soleil, vraies ombres, espacement anti-ombrage
- **Latitude** déduite du centroïde du tracé.
- **Espacement des rangées** (pas centre-à-centre) calculé par la géométrie solaire :
  - `rise = petit côté (1,303 m) × sin(tilt)`
  - élévation de **design** = midi au **solstice d'hiver** ≈ `90° − |lat| − 23,44°`
    (≈ 33° à Casablanca, lat 33,5°)
  - `ombre = rise ÷ tan(élévation_design)`
  - `pas ≥ empreinte (1,303 × cos tilt) + ombre + marge` → aucune rangée n'ombre la suivante
    à l'angle de design.
- **Soleil d'affichage** : matin clair (azimut = visée − 45°, à l'est), élévation liée à la
  latitude et **supérieure** à l'élévation de design → ombres bien visibles ET jour de soleil
  entre les rangées (on VOIT que l'ombrage a été géré). Vraies ombres portées (panneaux,
  châssis, lest) sur le toit et entre rangées (PCFSoftShadowMap).

## 4. Fidélité visuelle
- Châssis triangulaires (montant arrière haut / avant bas), rails, **lest béton** aux coins.
- Soleil directionnel + ambiance ciel + ombres douces ; matériaux PBR ; massing bâtiment
  propre ; satellite en sol. **InstancedMesh** pour tous les éléments répétés.
- **LOD léger** : appareils modestes (≤ 4 cœurs ou ≤ 4 Go) → ombres 1024 px + sans antialias ;
  sinon 2048 px + antialias.

## Constantes clés (`src/lib/roofPro2.ts`)
| Constante | Valeur | Rôle |
|---|---|---|
| `PANEL2_LONG_M` / `PANEL2_SHORT_M` / `PANEL2_THICK_M` | 2.384 / 1.303 / 0.033 | dimensions réelles |
| `PANEL2_WATT` | 720 | puissance crête / panneau |
| `PANEL2_TILT_DEG` | 13 | inclinaison toit plat |
| `SOLAR_DECLINATION_DEG` | 23.44 | déclinaison solstice (espacement) |
| `PERIMETER_SETBACK_M` | 0.5 | retrait de rive |

## Périmètre honnête
Installation **physiquement crédible** (vrai panneau, vrai sud, vrai soleil, rangées espacées
par le soleil) sur un **volume de bâtiment approximatif** (contour tracé + étages). On ne
reconstruit PAS la maison réelle. Jamais un devis : une fourchette indicative.

## Source
Datasheet constructeur Canadian Solar TOPBiHiKu7 (CS7N-TB-AG). Specs reprises du datasheet ;
aucune image copiée.
