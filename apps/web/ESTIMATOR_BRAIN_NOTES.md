# ESTIMATOR_BRAIN_NOTES — le « cerveau » de l'estimateur piloté par la facture

Méthode et hypothèses du module `src/lib/estimatorBrain.ts` (preview privé
`/preview/toiture-3d-pro-3`). C'est de la **méthode**, pas de la donnée client —
committé exprès. Rien ici n'est un devis : une fourchette indicative.

## 1. Espacement inter-rangées = fonction de l'inclinaison (règle solstice d'hiver)

Une rangée ne doit pas ombrer la suivante au moment de référence. Pas (pitch) :

    D = L · [ cos(β) + sin(β) · cos(γ_s) / tan(α_s) ]

- `L` = longueur du panneau **dans le sens de la pente** (portrait : 2,384 m ;
  paysage : 1,303 m).
- `β` = inclinaison.
- `α_s` = **élévation** solaire, `γ_s` = **azimut écart au sud** au moment de design.
- Position solaire calculée maison (aucune dépendance, ~12 lignes), latitude du toit :
  - déclinaison solstice d'hiver `δ = −23,44°` ; angle horaire `h = 15°·(heure_solaire − 12)` ;
  - `sin(α) = sin(φ)·sin(δ) + cos(φ)·cos(δ)·cos(h)` ;
  - `sin(γ) = −cos(δ)·sin(h)/cos(α)`.
- **Moment de design** = fenêtre solstice d'hiver 10 h–14 h (standard pro, défaut
  HelioScope). On prend le **soleil de 10 h** (point le plus défavorable de la
  fenêtre) → exposé en constante `DESIGN_SOLAR_HOUR = 10` ; passer à 12 h (« midi
  solaire ») donne une règle plus dense, échangeable en un seul endroit.

**Ancrages de validation (Casablanca φ≈33,6°, 29°, portrait L=2,384) :**
midi → pas ≈ 3,9 m (GCR ≈ 0,62) ; 10 h → pas ≈ 4,1 m (GCR ≈ 0,58). Le code
reproduit les deux au centième (testé). Baisser β de 29° → 15° → 10° resserre le
pas → beaucoup plus de rangées : c'est tout l'intérêt, visible dans les comptes.

**UNE seule fonction d'ombre pour TOUTES les configs (correctif 2026-06).** Le
terme d'ombre `ombre = rise · (composante directionnelle)/tan(α_s)`, avec
`rise = L·sin β`, est partagé :
- **Sud** (rangées E-O empilées vers le sud) : composante = `cos(γ_s)`.
- **Est-Ouest** (chevrons N-S empilés vers l'est) : composante = `|sin(γ_s)|`. Le
  soleil de design (10 h, SE) projette ses ombres vers le NW ; la composante de
  blocage **est-ouest** entre chevrons est donc le **sinus** de l'azimut, pas le
  cosinus — plus petite, d'où un intervalle plus serré à basse inclinaison, mais
  **calculé**, jamais une densité/GCR codée en dur.

**Pavage de vrais rectangles, pas une surface × ratio.** Chaque panneau est un
rectangle `(L·cos β) × largeur` pavé dans le tracé (après retrait + obstructions) ;
on compte les panneaux qui tiennent réellement. Borne physique dure (testée sur
chaque config) : **Σ empreintes au sol ≤ surface utile** — les panneaux ne peuvent
pas se superposer, donc un compte E-O aberrant est mathématiquement impossible.
**Cohérence E-O vs Sud à inclinaison égale (correctif 2026-06)** : à inclinaison
ÉGALE, les chevrons E-O dos à dos récupèrent l'intervalle d'ombre que le Sud
gaspille → **compte E-O ≥ compte Sud** (vérité physique testée sur toit à aspect
neutre ; les deux convergent quand l'inclinaison → 0). L'ancien garde-fou « 1,2–1,4× »
était une heuristique dépendante de la forme du toit — remplacé par « E-O ≥ Sud à
inclinaison égale » + la borne Σ empreintes ≤ surface utile.

**Correctif de rive (bug flottant).** `sin(180°) ≈ 1e−16` rendait les vecteurs de
base légèrement imprécis : les cellules pile au retrait calculaient une distance de
`0,5 − ε` et étaient rejetées → **toute la 1re rangée et la 1re colonne** étaient
perdues, asymétriquement entre Sud et E-O. Sur les petits toits, ce seul bug gonflait
le ratio à 1,7–2,4×. Corrigé par une tolérance `EDGE_EPS = 1 mm` sur la comparaison
au retrait ; les comptes Sud et E-O sont désormais corrects et cohérents.

## 2. Configurations évaluées

- **A. Sud @ inclinaison optimale** (≈29–30°, lue dans la table PVGIS pour la
  latitude exacte). Meilleur rendement/panneau, pas le plus large, moins de panneaux.
- **B. Sud @ inclinaison basse** — 15° et 10°. Plus de panneaux, rendement/kWc
  légèrement moindre.
- **C. Est-Ouest @ 10° (et 15°)** — dos à dos, rangées N-S, faces E et O. Densité
  kWc maximale (pas quasi nul à basse inclinaison ; les paires se « tentent »).
  Production = somme des deux sous-champs (aspect −90° et +90°). Suppose un
  onduleur double-MPPT (Deye/Huawei de la page /équipement).
- **D. « Énergie totale max sur CE toit »** — balayage de l'inclinaison sud de 5°
  à 30°, on retient l'angle qui maximise la **production totale du toit** (pas le
  rendement par panneau). Sur un toit limité en surface, atterrit **sous 29°** car
  plus plat = plus de panneaux. Affiché : « Rendement max par panneau : ~29°.
  Énergie totale max sur CE toit : ~X°. »

Portrait **et** paysage sont calculés pour chaque config ; on garde l'orientation
qui pose le plus de panneaux sur CE tracé. Défaut d'affichage : portrait (norme
toit plat marocain), mais le compte paysage est toujours montré.

## 3. Productible (PVGIS) + table committée

- Source vive : **PVGIS PVcalc** (JRC, Commission européenne — gratuit, sans clé,
  couvre le Maroc), via la route serveur `/api/roof-yield` (le navigateur n'appelle
  jamais PVGIS). Paramètres : `peakpower`, `loss=14`, `angle=β`, `aspect`,
  `pvtechchoice=crystSi`, `mountingplace=building`. C'est la MÊME intégration que
  `roofEstimate.ts` (route existante `/api/roof-estimate` inchangée), étendue pour
  accepter l'inclinaison.
- **Table committée** : `src/lib/yieldTable.ts`, générée par
  `scripts/generate-yield-table.mjs` (vraies valeurs PVGIS) pour les 5 latitudes de
  service (Agadir, Marrakech, Casablanca, Rabat, Tanger) × inclinaisons {0,5,10,15,
  20,25,29,30,35} × azimuts {0,−45,45,−90,90}. L'estimateur interpole entre les
  deux villes encadrant la latitude du toit → **instantané** (aucun appel réseau
  par réglage).
- **Chaîne de repli** : PVGIS live (mis en cache côté client par config) → table
  committée (interpolée) → « estimation indisponible ».
- **Pertes** : 14 % (défaut PVGIS, valeur déjà utilisée par le site —
  `roofEstimate.ts`). Non modifiée en silence.
- Bande de cohérence Casablanca sud-optimal : la table donne ≈1 650 kWh/kWc/an
  (dans la fourchette 1 650–1 900 après pertes ; bas de fourchette, normal).

## 4. Facture → énergie → économies (barème RÉGIE ONEE TTC, corrigé W11 2026-06-17)

Une seule fonction `billMAD(monthlyKwh, grid?)` — coût ÉNERGIE de la grille `grid`
(défaut **`REGIE_TARIFF`**), bloc de config unique dans `estimatorBrain.ts` (copié à
l'identique dans `estimatorBrainV2.ts`).

**Barème RÉGIE ONEE « usage domestique », prix consommateur TTC (TVA 20 % DÉJÀ incluse
— ne JAMAIS rajouter de TVA par-dessus), juin 2026, fourni et vérifié par le fondateur :**

- **≤ 150 kWh/mois — progressif** : 0,9010 sur les 100 premiers kWh + 1,0732 sur 101–150.
- **> 150 kWh/mois — sélectif** (TOUTE la conso au tarif de sa tranche) :
  151–210 → 1,0732 · 211–310 → 1,1676 · 311–510 → 1,3817 · > 510 → 1,5958 MAD/kWh.
- **Bornes effectives 210/310/510** : la **tolérance de 10 kWh** intégrée
  (`boundaryToleranceKwh`) décale les bornes nominales 200/300/500 → 210/310/510 (on
  n'entre dans la tranche supérieure qu'à +10 kWh).
- **Garantie de monotonie** (un client à 511 kWh ne paie jamais moins qu'à 510). Frais
  fixes (TPPAN, redevances) NON modélisés : invariants au solaire, ils s'annulent dans
  les économies.

> **Correctif W11.** L'ancienne grille sélective (201–300 = 1,18 ; 301–500 = 1,45 ;
> > 500 = **1,66**) était trop haute : **1,66 était le tarif FORCE-MOTRICE, pas le
> domestique**. Le bill→conso et la logique d'économies sont **inchangés** ; seules les
> tranches/bornes ont été corrigées.

- **Deux régimes au Maroc.** Le barème **RÉGIE/gouvernement** ci-dessus (Marrakech,
  Agadir, El Jadida et toutes les zones ONEE/régie) **et** des grilles contractuelles
  plus chères dans les trois villes **ex-délégataires** (Casablanca/Lydec,
  Rabat/Redal, Tanger/Amendis). `TARIFF_BY_CITY` mappe chaque ville à sa grille et
  `tariffForCity(city)` la résout. **POUR L'INSTANT toutes les villes (y compris les
  trois délégataires, entrées explicites du map) sont égalées au barème RÉGIE** — défaut
  **conservateur** qui sous-estime légèrement les économies en zone délégataire (jamais
  l'inverse). Primes réelles connues à caler plus tard (commentées dans le code) :
  Casablanca ≈ **+10,5 %** sur le haut de grille, Tanger la **plus chère**, Rabat la
  **moins chère**. Les grilles délégataires **exactes attendent une vraie facture
  récente par ville** (gate WG2 partiellement résolu).

- **Facture → conso annuelle** : on **inverse numériquement** `billMAD` (recherche
  binaire), ×12. Pour une grosse facture, ceci donne le tarif effectif de la tranche
  haute. *Valeurs pinées (tests) : ~135 MAD/mois → ~141 kWh/mois (progressif) ;
  ~480 MAD/mois → ~347 kWh/mois (311–510) ; ~1 480 MAD/mois → ~927 kWh/mois
  (~11 100 kWh/an, > 510).*
- **Économies/an = [ billMAD(conso) − billMAD(conso − autoconsommé) ] × 12** — la vraie
  réduction de la facture énergie. Plafond **automatique et plus serré** : ≤
  billMAD(conso) (le coût énergie évitable), jamais au-delà. Surplus au-delà de la
  conso = 0 (pas de net-billing BT clair au Maroc — conservateur). Fourchette basse
  = 75 % (alignement temporel réel de l'autoconsommation).

> ⚠️ **Délégataires à caler sur une vraie facture.** Le barème régie est confirmé ; les
> grilles Lydec/Redal/Amendis exactes se déposeront dans `TARIFF_BY_CITY` en un seul
> endroit dès qu'une vraie facture récente par ville sera disponible. Le reste du site
> (résidentiel/professionnel) partage désormais ce **barème régie** comme base.

## 5. Bifacial

Le panneau est bifacial, mais **tous les chiffres de tête sont face avant
(équivalent monoface)** — défendable et traçable. Une ligne optionnelle clairement
étiquetée « + gain bifacial (estimation prudente) » peut s'afficher avec un
coefficient documenté (`BIFACIAL_GAIN` : +5 % en sud incliné bien espacé, moindre
en pose dense/plate), **jamais** fondu dans le chiffre de tête.

## 6. Algorithme de recommandation (le cœur)

1. `cible = facture → conso annuelle`.
2. `prod_best` = production de la config A (sud @ optimal) sur CE toit, meilleure
   orientation portrait/paysage.
3. Si `prod_best ≥ cible` → **Sud @ optimal, dimensionné au besoin** : poser juste
   assez de rangées pour couvrir `cible × 1,1` (plafonné au max du toit). Message :
   « 29° plein sud est optimal pour votre latitude et couvre votre consommation —
   aucun compromis ; il reste de la place sur le toit. »
4. Sinon (toit trop petit à l'espacement optimal) → **densifier**, en s'arrêtant à
   la première config qui atteint la cible : (i) baisser le sud 29°→15°→10° ;
   (ii) Est-Ouest 10°, puis 15°. Recommander la config de **meilleure qualité**
   (la plus proche de 29° sud) qui atteint la cible.
5. Si même l'E-O max < cible → recommander l'E-O max densité et le dire
   honnêtement : « Ce toit plafonne à ~X kWh/an, soit ~Y % de votre consommation. »
6. Toujours renvoyer le **comparatif complet** de toutes les configs ; la 3D se
   re-rend pour celle que le client choisit.

Toute la géométrie + la décision est **pure et testée** (`tests/estimatorBrain.test.ts`).
Le rendu 3D réutilise le modèle panneau Canadian Solar 720 W de `toiture-3d-pro-2`.
