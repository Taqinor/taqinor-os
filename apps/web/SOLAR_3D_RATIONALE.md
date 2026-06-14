# Géométrie du rendu 3D « réaliste » — estimateur de toiture pro

Note de conception du preview privé **`/preview/toiture-3d-pro`** (rendu Three.js
des panneaux inclinés sur châssis triangulaires lestés, en rangées). Elle fige les
décisions géométriques pour qu'elles soient relues et ajustables d'un seul endroit.

> Résumé d'une ligne : panneaux **paysage inclinés à 12°** vers l'orientation
> choisie, posés sur des **châssis triangulaires** (montant arrière haut, avant
> bas) **lestés de plots béton**, en **rangées parallèles** au pas =
> empreinte du panneau incliné **+ 1,5 × sa hauteur projetée** (anti-ombrage).

## Pourquoi ce modèle (toiture plate — cas par défaut au Maroc)

Sur toit plat, les panneaux ne sont pas posés à plat : ils sont **relevés** sur des
supports inclinés, **lestés** (non perforants) pour résister au soulèvement par le
vent, et alignés en **rangées espacées** pour ne pas se faire de l'ombre. C'est ce
que rend la version « pro ».

### Inclinaison (tilt) — `PANEL_TILT_DEG = 12`
- Plage retenue : **10–15°**, typique des systèmes lestés *optimisés en densité*.
  Un angle faible réduit la prise au vent (donc le lest nécessaire) et resserre les
  rangées → plus de kWc sur la même surface. Les angles plus forts (15–35°)
  produisent un peu plus par panneau mais imposent des rangées bien plus écartées
  (moins de panneaux). 12° est un bon compromis densité/production pour le Maroc.
- Constante unique, triviale à changer : `PANEL_TILT_DEG` dans `src/lib/roofPro.ts`.
- Les panneaux s'inclinent **vers l'orientation sélectionnée** (Sud par défaut) :
  bord arrière haut côté opposé au soleil, bord avant bas côté soleil.

### Châssis triangulaire
- Profil **triangle rectangle** : **montant arrière haut**, **montant avant bas**,
  reliés par l'hypoténuse qui porte le panneau à l'inclinaison. C'est la silhouette
  reconnaissable d'un système lesté ; elle doit rester **bien visible à l'orbite**.
- Hauteur projetée d'un panneau incliné (dimension « montée ») :
  `rise = profondeur_panneau × sin(tilt)`. Avec un panneau paysage (1,0 m dans le
  sens de la pente), `rise ≈ 1,0 × sin(12°) ≈ 0,21 m`.
- Matière : aluminium / gris anthracite, fines barres.

### Lest (ballast)
- Petits **plots béton** au pied avant de chaque châssis. Discrets mais présents :
  c'est ce qui fait « lire » un vrai système non perforant. Gris béton mat.
- Référence métier : 4–8 lb/pi² de lest selon la zone de vent ; ici purement visuel.

### Rangées et pas inter-rangées — `ROW_GAP_RISE_FACTOR = 1.5`
- Rangées **parallèles**, toutes orientées pareil.
- **Pas de rangée** (centre à centre, dans l'axe de la pente) :
  `pas = empreinte_profondeur + 1.5 × rise`
  où `empreinte_profondeur = profondeur_panneau × cos(tilt)`.
  Règle métier courante : espacer de **1,5 à 2 ×** la hauteur des panneaux inclinés
  pour éviter l'ombrage inter-rangées aux heures pleines. On retient 1,5×.
- Retrait de rive (périmètre) : `PERIMETER_SETBACK_M = 0.5` (maintenance + sécurité).

### Comptage = ce qui est dessiné (précision assumée)
Le calepinage espacé/incliné détermine **combien de panneaux entrent réellement** →
ce nombre pilote kWc → production PVGIS → fourchette d'économies. C'est **plus juste**
que l'ancien calepinage « collé à plat » : le nombre peut sortir **un peu plus bas**
(les vraies rangées exigent des jeux). Les chiffres affichés correspondent au champ
réellement modélisé, et le pré-remplissage du lead (surface / orientation / kWc)
reste cohérent avec ce champ.

## Toiture en pente (bascule « villa »)
Pose **affleurante**, parallèle au rampant (montage sur rails, **sans** châssis
triangulaire ni lest), en rangées régulières. Réaliste pour un toit incliné. Le
volume du bâtiment reste un **massing approximatif** (emprise tracée + nombre
d'étages), pas une reconstruction photo-réaliste de la maison exacte.

## Périmètre honnête
Le **montage** est rendu de façon réaliste (inclinaison, châssis, lest, rangées,
ombres douces). Le **bâtiment** reste un volume propre mais approximatif déduit du
contour tracé et du nombre d'étages — ce n'est pas une copie fidèle de la maison.

## Constantes (toutes dans `src/lib/roofPro.ts`)
| Constante | Valeur | Rôle |
|---|---|---|
| `PANEL_TILT_DEG` | 12 | inclinaison des panneaux (toit plat) |
| `ROW_GAP_RISE_FACTOR` | 1.5 | jeu inter-rangées = facteur × hauteur projetée |
| `PERIMETER_SETBACK_M` | 0.5 | retrait de rive |
| `FRONT_STRUT_M` | 0.08 | hauteur du montant avant (bas) |
| `BALLAST_*` | — | dimensions des plots béton (visuel) |

Dimensions panneau et puissance crête réutilisées telles quelles depuis
`src/lib/roof.ts` (`PANEL_LENGTH_M` 1,7 / `PANEL_WIDTH_M` 1,0 / `PANEL_WATT` 550),
afin que la « pro » et les versions 2D/3D parlent du même panneau.

## Sources (technique, aucune image copiée)
- AltEnergyMag — *Solar on Flat Roofs: Ballasted, Attached & Hybrid* (angles faibles
  pour la densité ; rangées plus écartées pour le rendement).
- *Flat Roof Solar Installation Guide* (SolarTech) — espacement 1,5–2 × la hauteur
  des panneaux inclinés contre l'ombrage inter-rangées.
- Mibet / IronRidge BX — systèmes lestés non perforants : plots béton contre le
  soulèvement, montage sans perçage.
