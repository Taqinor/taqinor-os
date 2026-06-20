# APPLIANCES_NOTES.md — typiques d'appareils du mode « Affiner ma consommation » (W68)

Ce mode laisse le client **affiner sa courbe de consommation horaire** sur la
prévisualisation privée `/preview/toiture-3d-pro-11`. Toutes les valeurs ci-dessous
sont des **fourchettes publiées de puissance typique** servant uniquement de **point de
départ éditable** : **la plaque signalétique du client prime toujours**. Rien ici n'est
asserté comme un fait sur l'installation d'un client donné — ce sont des ordres de
grandeur pour pré-remplir un calculateur que le client ajuste.

Les nombres alimentent la logique pure de `src/lib/applianceConsumption.ts` (testée dans
`tests/applianceConsumption.test.ts`). Aucun **nouveau tarif** n'est introduit : les
économies passent par le modèle existant `annualSavingsMad`/`billMAD`
(`src/lib/estimatorBrainV2.ts`, barème RÉGIE ONEE), surplus valorisé à zéro, plafonné par
la facture. La production horaire vient de **PVGIS** (`typicalDayByMonth` du moteur de
production W49/W50).

## Conventions

- **Énergie d'un appareil** : `kWh = W × h ÷ 1000` (puissance constante sur sa durée
  d'usage). Distribuée **uniformément** sur les heures de son créneau.
- **Climatisation** : entrée par puissance frigorifique en **BTU/h**, convertie en watts
  électriques par `W = BTU/h ÷ EER`. Au Maroc les climatiseurs se vendent en **chevaux
  (CV)** : on étiquette donc chaque preset BTU avec son équivalent CV
  (**≈ 9 000 BTU = 1 CV**), plus un champ libre.
- **« Sur ma facture actuelle » (onTop)** vs **« Déjà compris dans ma facture » (inBill)** :
  un appareil `onTop` (clim/voiture neuve pas encore reflétée dans la facture) **augmente
  le total journalier** (donc le besoin de panneaux et la batterie) ; un appareil `inBill`
  ne sert qu'à **reshaper la distribution horaire** en **gardant le total fixe**.

## Catalogue (défauts éditables)

| Appareil | Puissance typique | Usage / cycle | Créneau par défaut | Prise en compte | Note |
|---|---|---|---|---|---|
| Climatisation | BTU ÷ EER (EER ≈ 9 non-inverter, ≈ 12 inverter) | 9 000 / 12 000 / 18 000 / 24 000 BTU (≈ 1 / 1,5 / 2 / 3 CV) | après-midi → soir | onTop | Conversion BTU→W éditable. |
| Recharge voiture électrique | chargeur 2,3 / 3,7 / 7,4 / 11 / 22 kW (7,4 kW = wallbox monophasé courant) — ou km/jour × ~17 kWh/100 km | h/jour ou km/jour | nuit / midi solaire / soir | onTop | Recharger en plein soleil augmente fortement l'autoconsommation. |
| Chauffe-eau électrique (cumulus) | ~1 500–3 000 W | ~2–3 h/jour | matin/soir ou heures creuses | inBill | Beaucoup de foyers marocains chauffent l'eau au gaz (butane) — optionnel. |
| Pompe de piscine | ~750–2 000 W | 4–8 h/jour | midi | inBill | |
| Four électrique | ~2 000–2 500 W | ~1 h/jour | soir | inBill | |
| Plaque / cuisinière électrique ou induction | ~1 500–3 000 W | aux repas | midi & soir | inBill | Le gaz reste courant au Maroc. |
| Lave-linge | ~500 W moyen (~1 kWh/cycle) | ~0,5–1 cycle/jour | matinée | inBill | |
| Lave-vaisselle | ~1 200–2 400 W (~1–1,5 kWh/cycle) | ~1 cycle/jour | soir | inBill | |
| Sèche-linge | ~1 800–3 000 W (~2–3 kWh/cycle) | ~1 cycle/jour | journée | inBill | |
| Réfrigérateur / congélateur | ~100–400 W | 24 h continu (~1–2 kWh/jour) | toute la journée | inBill | Socle permanent. |
| Chauffage électrique / radiateur | ~500–2 400 W | matins/soirs d'hiver | soir | onTop | |
| Pompe à eau / forage | ~750–1 500 W | intermittent | journée | inBill | Villas / rural. |
| Fer à repasser | ~1 000–1 800 W | court | soir | inBill | |
| Micro-ondes | ~600–1 200 W | court | midi/soir | inBill | |
| Pompe à chaleur (chauffage/refroidissement) | configurable | selon saison | après-midi/soir | onTop | |
| Téléviseur + électronique | petit agrégat | soirée | soir | inBill | |
| Éclairage LED | petit agrégat | soirée | soir | inBill | |
| Autre appareil | champ libre (nom + W + heures + créneau) | — | — | — | Ligne libre éditable. |

## Constantes physiques / opérateur

- **EER par défaut** : ~9 (non-inverter), ~12 (inverter) — éditables.
- **9 000 BTU ≈ 1 CV** (équivalence commerciale marocaine usuelle).
- **Recharge VE** : conso de référence **~17 kWh/100 km**, éditable.
- **Batterie** : capacité utile retenue **6 kWh/jour par batterie** (constante opérateur),
  dimensionnement « taille-au-besoin » : nombre de batteries =
  plafond(énergie soir/nuit décalable depuis le surplus solaire ÷ 6 kWh/jour). On ne stocke
  jamais plus que le surplus réellement produit.

## Silhouette de base (forme uniquement)

La courbe de départ (`BASELINE_SHAPE`) est une **silhouette** résidentielle plausible
(creux la nuit, bosse du matin, pic du soir) **normalisée** : ce sont des **poids de
forme**, pas des kWh. Le **total réel** vient toujours de la facture
(`billToAnnualKwh ÷ 365`). Le client peut ensuite tout éditer à la main (glisser les
barres ou saisir les valeurs) et « Recaler sur ma facture » pour ré-imposer ce total.
