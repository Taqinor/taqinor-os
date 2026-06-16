# BRAIN V2 — notes de méthode (estimateur toiture, preview privé pro-4)

Notes d'ingénierie (pas de données client). Audit du cerveau actuel
(`src/lib/estimatorBrain.ts`, consommé UNIQUEMENT par `/preview/toiture-3d-pro-3`)
puis plan de la V2 livrée sur une NOUVELLE route privée `/preview/toiture-3d-pro-4`.

## 1. Logique d'inclinaison aujourd'hui (pro-3)

`recommend()` évalue 5 configs fixes :
`south-opt` (≈ optimal annuel, ~29–30°), `south-15`, `south-10`, `ew-10`, `ew-15`.

L'espacement de rangée dépend de l'inclinaison via `rowPitchM()` (Sud) et de la
règle d'ombre de faîte E-O dans `packConfig.cellFor` — confirmé : plus c'est plat,
plus le pas est court, donc plus de panneaux tiennent. Cette physique est CORRECTE
et RÉUTILISÉE telle quelle.

`recommend()` calcule aussi un balayage Sud 5°→30° pas de 1° et expose
`maxRoofEnergyTiltDeg` / `maxRoofEnergyKwh`. **Constat clé : ce balayage est
calculé mais SEULEMENT AFFICHÉ (ligne « énergie totale max sur ce toit »). Il ne
pilote PAS la recommandation.** Sur un toit limité, la reco saute directement à
l'Est-Ouest (branche « plafond toit ») sans jamais proposer une inclinaison Sud
plus plate qui logerait davantage de panneaux — exactement le levier que le
propriétaire veut capturer.

## 2. Orientation / disposition / inclinaison (composition)

Côté écran (`roof-tool-pro3.ts`) la matrice EXISTE déjà et est correcte :
- `placedFor(grid) = neededPanels>0 ? min(neededPanels, grid.count) : grid.count`
  applique le plafond « besoin » à TOUTE config, recommandée OU manuelle.
- orientation (`data-family`), disposition (`data-orient` auto/portrait/paysage)
  et inclinaison (`data-tilt` reco/preset) sont des bascules indépendantes qui
  repassent par `renderSelection()` (re-rendu sans recalcul du cerveau).

**Bug de couplage trouvé dans le CERVEAU (pas l'écran) :** la branche « densifie »
de `recommend()` (sud-opt ne couvre pas mais sud-15/10/ew couvre) renvoie
`{...pick}` avec le compte PLEIN du toit à cette inclinaison — **non plafonné au
besoin**, contrairement à la branche « couvre à l'optimal » qui, elle, plafonne
(`min(configA.count, ceil(kwcNeeded/…))`). L'écran re-plafonne via `placedFor`, donc
l'affichage final est sauf, mais l'objet `rec.recommended` (compte/kWc/kWh/
économies du bandeau) sur-estime dès qu'on densifie. C'est la même classe de bug
que « un chemin manuel rend la pleine capacité au lieu de la cible plafonnée ».

## 3. Algorithme de reco vs plafond « besoin »

`neededPanelsForTarget(target, lat)` = besoin dicté par la facture (cible +10 % au
rendement Sud optimal), indépendant du toit. Règle dure du propriétaire :
**panneaux posés = min(besoin, ce qui tient)** — jamais au-dessus. Le surplus
au-delà de l'autoconsommation vaut 0 (pas de net-billing BT clair au Maroc), donc
dépasser le besoin n'est jamais recommandé ni auto-placé.

## 4. Couverture de tests — points faibles

`tests/estimatorBrain.test.ts` couvre bien : physique d'espacement, ONEE
sélectif, bornes d'empreinte, obstacles, plafond « besoin » composé. **Trous :**
aucun test ne vérifie que la reco CHOISIT une inclinaison plus plate sur toit
limité, ni qu'elle GARDE l'optimal sur toit spacieux (pas de sur-remplissage), ni
la cohérence capée de l'objet `recommended` dans la branche densifie.

## 5. Plan V2 (isolation propre)

**Isolation : copie versionnée.** `estimatorBrain.ts` n'est importé que par pro-3.
On copie → `src/lib/estimatorBrainV2.ts` et on n'améliore QUE la V2. pro-3 reste
**octet pour octet identique** (cerveau, script, page inchangés). pro-4 importe la
V2. Géométrie partagée (`roof.ts`, `roofPro2.ts`, `yieldTable.ts`) réutilisée, pas
dupliquée.

**Améliorations V2 :**
1. `tiltSweepSouth()` : balayage fin (5°→optimal, pas ~2°) qui, pour le toit donné,
   calcule pour chaque inclinaison la production des panneaux POSÉS
   (`placed = min(besoin, fit)`) et renvoie l'inclinaison qui maximise cette
   production UTILE (capée). Objectif unique qui se comporte bien des deux côtés :
   - toit spacieux (fit ≥ besoin partout) → posés = besoin constant → maximise le
     rendement/kWc → garde l'optimal (~29°), zéro sur-remplissage ;
   - toit limité → aplatir augmente le fit plus vite que le rendement/kWc ne baisse
     → la production utile monte → choisit une inclinaison plus plate, MAIS plafonné :
     dès que fit atteint le besoin on s'arrête (on ne bourre pas de surplus).
2. `recommend()` réécrit autour d'un évaluateur unique `evalConfig()` qui renvoie
   TOUJOURS l'objet capé (posés = min(besoin, fit), prod/économies dérivés des
   posés). Plus de branche non-capée.
3. La reco compare {meilleur Sud du balayage} vs {meilleur E-O} sur la production
   utile capée ; départage : à production égale, préférer le meilleur rendement par
   panneau (Sud plus raide / moins de matériel). Message FR honnête quand une
   inclinaison plate gagne : « Incliné à ~X° pour loger plus de panneaux : +A % de
   production totale malgré ~B % de rendement/panneau en moins. »
4. pro-4 : contrôle d'inclinaison mobile-first (curseur 5–35° + bouton « reco »)
   qui repasse par le même chemin de re-rendu ; le plafond `placedFor` reste appliqué
   à chaque combinaison orientation × disposition × inclinaison.

**Garde-fous conservés sur toute la matrice :** plafond besoin jamais dépassé ;
E-O ≥ Sud à inclinaison égale ; Σ empreintes ≤ surface utile ; économies ≤ coût
énergie évitable ; dégagements obstacles honorés. Tests de régression : les
nombres de pro-3 ne bougent pas là où l'isolation l'exige (V2 reproduit la V1 sur
les cas déjà corrects, sauf les corrections explicites ci-dessus).
