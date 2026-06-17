# Cerveau V6 de l'estimateur — notes

Preview privé **`/preview/toiture-3d-pro-9`** (noindex, hors nav, exclu du sitemap,
non lié). Module pur `src/lib/estimatorBrainV6.ts`, testé
(`tests/estimatorBrainV6.test.ts`), **compose sur V2/V4/V5 sans en modifier un octet**
— pro-3..pro-8 restent des baselines intactes. V6 corrige **deux** choses de pro-8.

## FIX 1 — toit en pente = VRAI plan incliné (affleurant, sans châssis)

pro-8 gardait le **calepinage toit plat** et se contentait d'incliner chaque panneau
de la pente : tous les panneaux restaient **à la même hauteur** sur un toit
horizontal — un montage lesté à plat, pas une vraie pente. V6 fournit la **géométrie
pure et vérifiable** (le build ne voit pas la carte rendue → tout est ancré sur des
tests, pas sur l'apparence) :

- `roofPlaneNormal(pitch, facing)` — la normale du toit **penche vers la face** ;
  composante horizontale = `sin(pente)`, donc **plus le vecteur vertical dès que
  pente > 0**. C'est exactement la normale que `compose(yaw, tilt)` donne au panneau
  dans le rendu → les panneaux sont **coplanaires** au toit par construction.
- `pitchedDeckZ(...)` — la **surface de toit elle-même** devient un plan incliné :
  chaque sommet de la dalle est relevé à la hauteur du plan (pente × distance à
  l'égout). La photo détourée, mappée par **position horizontale**, reste géo-alignée.
- `flushPanelCenterAt(...)` / `flushPanelPose(...)` — chaque panneau est posé **sur le
  plan + un décalage CONSTANT** (`PITCHED_FLUSH_STANDOFF_M`, quelques cm) le long de la
  normale. Décalage identique pour tous → **pas de hauteurs variables** (= pas de
  châssis). Le centre **monte avec la pente** (vrai plan incliné).
- Le rendu pente (`flush=true`) n'instancie **AUCUN** châssis/lest : `front`, `back`,
  `rail`, `ballast` sont gardés par `if (!flush)`. Aucun espacement inter-rangées
  (coplanaire → aucune auto-ombre).

Référence d'égout = le point **le plus aval** du tracé (`eaveUpSlopeCoord`), pour que
la pente **monte à partir de l'égout** (rien sous le toit). Production pente inchangée :
PVGIS au seul (pente, face), pose `building` (V5), repli table « estimé ».

## FIX 2 — l'optimiseur balaie ET affiche la MATRICE complète (toit plat)

pro-8 ne montrait que ~6 configs nommées (V4). V6 `fineGridMatrixV6(...)` **balaie
dense** et **renvoie toutes les lignes** :

- inclinaison **0→35° par pas de 5°** (+ l'optimum Sud de la table) ;
- azimut **plein sud, aligné toit, et sud ±45° par pas de 15°** + le mode **Est-Ouest
  dos à dos** ;
- chacun en **portrait ET paysage**, marge **gardée/retirée** ;
- espacement inter-rangées **sans-ombre du solstice d'hiver conservé** (production
  honnête : un tilt plus plat loge plus de panneaux — ce compromis nombre↔tilt est
  exactement ce que le balayage surface) ;
- pour chaque combinaison : **panneaux posés, kWc, kWh/an (PVGIS au GPS exact, repli
  table « estimé »), % du besoin, fourchette d'économies**.

Le **RECOMMANDÉ** est le **vrai maximum sur tout le balayage** (énergie posée,
**plafonnée au besoin** — jamais sur-remplir un toit spacieux, le surplus n'est pas
rémunéré au Maroc), décrit comme sa propre ligne « Optimum calculé — inclinaison X°,
orientation Y, portrait/paysage » badgée **« Recommandé »**, épinglée en tête.

Le tableau (`paintComparison` dans `roof-tool-pro9.ts`) **affiche toute la matrice** :
triable par **kWh/an, panneaux, % du besoin** (`sortMatrix`), filtrable par
**orientation/pose** (`matrixGroupKey`), ligne recommandée épinglée + surlignée.
Cliquer une ligne la rend **exactement** en 3D (azimut span quelconque géré).

### PVGIS — rapide et dans les limites

Le **rendement spécifique** (kWh par kWc par an) par (tilt, azimut) étant
**indépendant de la taille**, le page-script préfetche
`pvgisMatrixCandidatePairs(...)` (kWc=1) **une fois par plan**, met en cache (cache
partagé `v4YieldCache`, clé tilt|aspect), **réutilise** sur tout le tableau et tous les
bascules, et **dégrade gracieusement** vers l'estimation maison (« estimé ») si PVGIS
est injoignable. La matrice estimée s'affiche **instantanément**, puis est affinée
PVGIS en asynchrone.

### Différé (à NE PAS construire sans modèle)

L'espacement inter-rangées / le taux d'occupation du sol (GCR) pourrait devenir un axe
d'optimisation supplémentaire, mais **seulement** avec un vrai modèle d'auto-ombrage
rangée-à-rangée que le moteur n'a pas encore (PVGIS chiffre **un** plan, pas
l'auto-ombrage). Resserrer l'espacement sous le seuil sans-ombre maintenant
introduirait de l'ombre non modélisée → **volontairement différé** pour garder chaque
chiffre honnête.

**Jamais un devis : une fourchette indicative.** La clé carte lue par la route est
`PUBLIC_MAPTILER_KEY` (option `PUBLIC_MAPBOX_TOKEN`) via `/api/roof-config`.
