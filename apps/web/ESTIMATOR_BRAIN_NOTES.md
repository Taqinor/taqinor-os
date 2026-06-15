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

## 4. Facture → énergie → économies (base RÉUTILISÉE du site)

Le site chiffre déjà l'énergie et les économies avec (dans `src/lib/roof.ts`,
aligné `billRange.ts`) :

- **Tarif** `TARIFF_MAD_PER_KWH = 1,4` MAD/kWh (tarif moyen).
- **Productible de repli** 1 600 kWh/kWc/an.
- **Économies** = 60–90 % de la valeur produite (autoconsommation).

Le cerveau réutilise EXACTEMENT cette base pour ne pas diverger du reste du site :

- **Facture → consommation annuelle cible** :
  `conso_annuelle_kWh = facture_mensuelle_MAD × 12 / 1,4`.
- **Économies** : `annualSavingsBandMad()` de `roof.ts` (60–90 %), inchangé.

> ⚠️ **NOMBRE À CONFIRMER PAR REDA.** Le 1,4 MAD/kWh est un tarif **moyen**. Le
> solaire efface d'abord le kWh le plus cher (tranches hautes Lydec/ONEE, souvent
> ~1,5–1,8 MAD/kWh marginal en résidentiel). Utiliser le marginal *augmenterait*
> les économies affichées. On garde 1,4 pour rester **cohérent avec le reste du
> site** ; à valider/ajuster en un seul endroit (`roof.ts`).

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
