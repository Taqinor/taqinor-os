# Cerveau estimateur V5 — méthode & sources (apps/web)

Documente la MÉTHODE derrière le preview privé `/preview/toiture-3d-pro-8`
(`src/lib/estimatorBrainV5.ts` + le câblage `src/scripts/roof-tool-pro8.ts`).
Aucune donnée client ici — uniquement la traçabilité. Rien sur un preview n'est
un devis : toujours une fourchette indicative.

## Ce que V5 ajoute (par rapport à pro-7 / V4)

pro-8 est un clone de pro-7 (toit plat = optimiseur V4 inchangé). V5 cible le
**toit en pente / tuiles**, **choisi AVANT le tracé** :

1. **Type de toit d'abord.** L'écran demande « toit plat » ou « toit en pente /
   tuiles » **avant** l'adresse et le tracé (Étape 2). Les puces partagent
   l'attribut `data-rooftype` avec le panneau de config (toutes câblées au même
   `setRoofType`). Plat → optimiseur V4 (grille fine PVGIS) **strictement
   inchangé**. Pente → pose affleurante.

2. **Pente = inclinaison, face = azimut, imposés par le toit.** Rien à optimiser.
   La pente est **saisie** (non mesurable sur l'imagerie top-down marocaine —
   Aurora/Sunroof s'appuient sur LiDAR + photogrammétrie HD, sinon tracé manuel +
   pente saisie), presets **15 / 22 / 30 / 45°** (curseur 5–45°). La face se
   confirme à la boussole de la carte.

3. **Production = PVGIS au seul (pente, face), pose `mountingplace = 'building'`.**
   Le page-script interroge `/api/roof-yield` (UNE jambe, `kWc=1` → rendement
   spécifique, mis à l'échelle), pose **« building »** (panneaux affleurants moins
   ventilés → tournent plus chaud → rendement légèrement plus bas, et reflète
   honnêtement une face/pente off-sud). Cache par (pente|face), réutilisé. PVGIS
   injoignable → **repli table committée** (`flushPlaneYield`/`specificYield`),
   carte étiquetée **« estimé »**. La jambe est construite par
   `pitchedPlaneLeg(pitch, facing, kwc)` (V5), aspect converti boussole → PVGIS via
   `aspectFromCompass` (V4).

4. **Aucun pas inter-rangées** (panneaux coplanaires → pas d'auto-ombre). Le pavage
   affleurant réutilise `packFlushPlane` (V3) : tuile dense, bornée par la surface
   utile, le retrait de rive et les keep-out d'obstacles ; portrait vs paysage selon
   ce qui loge le plus. **Un seul pan primaire** (multi-pans hors périmètre).

## 3D

Les panneaux sont rendus **affleurants, couchés à l'inclinaison = la pente**
(`renderScene(..., flush=true)`) : ils sont donc **coplanaires** au plan du toit
(invariant code-vérifiable). Le volume du bâtiment reste un schéma plat ; le rendu
d'un **deck incliné texturé** (photo satellite sur la surface inclinée) est
l'amélioration visuelle à **confirmer sur le téléphone** (la clé MapTiler/Mapbox
vit dans Cloudflare — l'agent de build ne peut pas afficher la carte).

## Invariants tenus

- **Pente = inclinaison de l'array**, **face = azimut de l'array** — imposés, jamais
  balayés ni optimisés.
- **Σ empreintes panneaux ≤ surface utile** (obstacles déduits) — via `packFlushPlane`.
- **Pas de pas de rangée solaire** en pente (coplanaire) — seulement un petit jeu de
  maintenance (`FLUSH_MAINTENANCE_GAP_M`).
- Pan orienté **nord** → sauté/signalé honnêtement (aucune pose recommandée).
- **Plafond besoin** + **plafond économies** (coût énergie évitable) tenus.
- Le **chemin toit plat reste celui de pro-7** (mêmes `recommend()` / `fineGridOptimum()`).

## Tests

- `tests/estimatorBrainV5.test.ts` (moteur pur) : presets incluant 45° ; pose
  `'building'` ; jambe PVGIS = une jambe à (pente, face) avec aspect boussole→PVGIS.
- `tests/estimatorPreviewPro8.test.ts` (page/route) : route privée (noindex, hors
  sitemap, hors page publique) ; **type de toit choisi AVANT le tracé** ; preset 45° ;
  pitched PVGIS pose `'building'` ; le proxy `/api/roof-yield` garde `'building'` par
  défaut ; baselines pro-3..pro-7 préservées.
