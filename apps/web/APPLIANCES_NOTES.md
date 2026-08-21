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
- **Batterie** : capacité utile retenue **6 kWh/jour par batterie** (constante opérateur,
  `BATTERY_KWH_PER_DAY` = `BATTERY_KWH_USABLE`), dimensionnement « taille-au-besoin » :
  nombre de batteries = plafond(énergie soir/nuit décalable depuis le surplus solaire ÷
  6 kWh/jour). On ne stocke jamais plus que le surplus réellement produit.
- **Coût batterie — ESTIMATION À CONFIRMER (W96)** : pour afficher un retour sur
  investissement **indicatif**, on retient une fourchette de **coût au kWh utile** de
  **~3 500 → ~6 000 MAD/kWh** (`BATTERY_COST_PER_KWH_MAD_LOW`/`_HIGH`, lithium LFP, pose
  comprise — marché marocain, **à confirmer par le founder**). Le retour sur investissement
  affiché = coût indicatif du parc ÷ **économie additionnelle réelle** que la batterie
  permet (report du soir), **jamais une économie fabriquée** : l'économie est plafonnée
  ailleurs au coût évité (`annualSavingsMad`/`billMAD`). Aucune économie nulle ne produit un
  payback (il reste indéfini). Tous ces nombres sont **indicatifs et éditables**.

## Intégration annuelle 12 mois (l'honnêteté du chiffre de tête — W82/W84/W95)

- **Autoconsommation ANNUELLE** : on **intègre sur les 12 mois réels**
  (`annualSelfConsumptionKwh`) — pour chaque mois, l'autoconsommation du **jour-type de
  production de CE mois** (`typicalDayByMonth[m]`, PVGIS) × le **nombre de jours du mois**
  (`DAYS_IN_MONTH`, Σ = 365), puis somme. Le chiffre de tête (économies, batterie) ne
  dépend donc **plus du mois affiché à l'écran** ; le graphe jour/mois reste « month-aware »
  uniquement pour **l'affichage**. Décembre (peu de soleil) compte moins, juillet plus.
- **Heures saisies → créneau (W84)** : la fin de créneau d'un appareil vient de la **durée
  saisie** (`slotEndHour(startHour, hours) = startHour + ceil(hours)`, ≥ 1 h, ≤ 24 h). Une
  clim/VE « 3 h » occupe **3 heures**, pas un créneau figé de 10 h — l'autoconsommation
  reflète les heures réelles d'usage.
- **Batterie annuelle (W84)** : la taille batterie est dérivée du **déficit du soir moyenné
  sur les 12 mois** (`annualBatterySizing`), bornée par le surplus de chaque mois — **stable**
  d'un mois à l'autre (la version mensuelle basculait/retombait à 0 selon le mois affiché).
- **Profil saisonnier été ≠ hiver (W95)** : un toggle façon `ete_differente`
  (`seasonalConsumptionByMonth(ref, summerFactor, winterFactor)`) **met à l'échelle le
  total journalier** l'été vs l'hiver (mois d'été = juin→sept., `SUMMER_MONTHS`) en
  **conservant la forme horaire**. Il nourrit l'intégrale 12 mois
  (`annualSelfConsumptionSeasonalKwh`) : une conso d'été plus forte change **honnêtement**
  l'autoconsommation annuelle. Le détail mensuel (`perMonthKwh`) alimente un **mini-graphe
  d'autoconsommation par mois** (SVG, hauteur réservée, sans CLS, mouvement réduit
  respecté).

## Silhouette de base (forme uniquement)

La courbe de départ (`BASELINE_SHAPE`) est une **silhouette** résidentielle plausible
(creux la nuit, bosse du matin, pic du soir) **normalisée** : ce sont des **poids de
forme**, pas des kWh. Le **total réel** vient toujours de la facture
(`billToAnnualKwh ÷ 365`). Le client peut ensuite tout éditer à la main (glisser les
barres ou saisir les valeurs) et « Recaler sur ma facture » pour ré-imposer ce total.

> `BASELINE_SHAPE` reste la silhouette de l'outil **« Affiner ma consommation »**
> (`/preview/toiture-3d-pro-11`). La **courbe journalière de `/proposition`**, elle, ne
> l'utilise plus : elle a ses trois silhouettes d'occupation (section suivante).

## Courbe journalière de `/proposition` — occupation, saison, Ramadan (CJ1, 21/08/2026)

Le graphe « Sur une journée » de la page proposition dessinait **une seule** silhouette
de consommation pour tout le monde et une cloche de production **synthétique** dont le
sommet était libellé « kWh » alors que c'est une **puissance**. Trois corrections, toutes
dans `src/lib/dayProfiles.ts` (pur, testé dans `tests/dailyCurvesCJ1.test.ts`) :

### 1. Trois silhouettes d'occupation au lieu d'une moyenne

`OCCUPANCY_SHAPES` porte **24 poids de forme** (jamais des kWh) pour chacun des trois
profils que le visiteur choisit par une puce :

| Profil | Qui | Signature |
|---|---|---|
| **Présent en journée** (`presence_jour`) | retraités, foyers mono-actifs, villa occupée | plateau diurne réel, midi marqué, pointe du soir la moins creusée |
| **Absent en journée** (`absence_jour`) | actifs partis au travail | pointe du matin (départ), creux diurne profond (9h-16h), pointe du soir la plus forte |
| **Présence partielle** (`presence_partielle`) | télétravail, mi-temps, foyer mixte | plateau diurne bas mais réel — **c'est le repli** quand le serveur ne dit rien |

Le **défaut** vient du drapeau serveur `courbes_journalieres.occupation` (décision
fondateur 21/08/2026 : la clientèle résidentielle réelle de TAQINOR est majoritairement
présente en journée, d'où `presence_jour` par défaut en résidentiel — c'est une
**observation de terrain**, pas une statistique nationale, et `occupation_source` le dit).

**Provenance de chaque heure** (étiquetée en commentaire dans le code) :

- **[A] fait marocain sourcé** — la fenêtre de pointe nationale est publiée : tarif
  bi-horaire ONEE **18h-23h en été / 17h-22h en hiver** (one.org.ma) ; record historique
  d'appel de puissance du réseau le **25/07/2019 à 21h45** (presse économique, Le Desk /
  Boursenews). La domination du soir n'est pas une hypothèse.
- **[S] motif de clustering sourcé, magnitude estimée** — la séparation présent/absent/
  partiel et l'allure de chaque groupe viennent de la littérature de clustering de courbes
  de charge résidentielles (étude sur données Dubaï, ScienceDirect S377877882300333X ;
  arXiv 2102.11027 ; IOPscience ade3fa). Les **valeurs exactes sont nos estimations**.
- **[i] interpolation** entre deux heures étiquetées ci-dessus.

### 2. Le NIVEAU vient du serveur, la FORME reste ici

`courbes_journalieres` sert, **par saison** (hiver = DJF, mi-saison = MAM+SON, été = JJA —
les mêmes bornes que `pvgis_profils.MOIS_PAR_SAISON`) :

- `production[saison].forme` — 24 parts PVGIS, heure locale, **somme = 1** ;
- `production[saison].kwh_jour` et `pic_kw` — énergie du jour moyen et **puissance** de
  l'heure de pointe, calculées côté serveur (productible PVGIS × kWc du devis) ;
- `consommation[saison].kwh_jour` — moyenne des **factures réelles** du lead.

`consumptionKwhShape(dailyKwh, …)` met la silhouette choisie à l'échelle de ce kWh/jour :
l'intégrale journalière vaut **exactement** le chiffre servi. C'est ce qui rend la phrase
« ajusté à votre facture » vraie et permet aux deux courbes de partager **un seul axe en
kW**. Bloc absent (le cas fréquent) ⇒ repli inchangé : cloche sin² + `prod_kwh/365` et
silhouette normalisée, avec la formulation prudente d'origine.

**Le pic est désormais libellé `kW` partout**, y compris sur le chemin de repli — c'est une
puissance moyenne d'heure de pointe, jamais une énergie.

### 3. Été et Ramadan : des MODIFICATEURS orthogonaux, calculés

- **Été (clim)** — ×1.5 sur **13h-21h** (la fenêtre s'arrêtait à 18h et coupait la moitié
  du phénomène : les guides d'usage de la climatisation et la fenêtre de pointe ONEE d'été
  situent la sollicitation des splits l'après-midi **et** en début de soirée). Le
  multiplicateur reste une **estimation**, à confirmer sur des factures d'été réelles.
  Reste une **puce** que le visiteur clique — la page ne décide jamais à sa place s'il
  climatise.
- **Ramadan** — les heures ne sont plus codées en dur (`3h-5h suhoor / 19h iftar`
  n'étaient vraies que pour un Ramadan d'été ; le mois recule de ~11 jours par an et tombe
  en hiver jusqu'en 2033). `ramadanWindow(date, lat, lon)` combine :
  - une **table des plages grégoriennes 2025→2033** (`RAMADAN_RANGES`, hégire 1446→1455),
    estimations astronomiques relevées sur **aladhan.com** et recoupées avec **sajda.com** ;
    le Maroc confirme le 1ᵉʳ jour par **observation lunaire**, d'où ±1 jour — sans effet, la
    table ne sert qu'à choisir un jour représentatif ;
  - le **coucher de soleil NOAA** au point GPS du chantier (repli Casablanca 33,57 / −7,59),
    exprimé en **UTC+0** : le Maroc repasse à UTC+0 **pendant le Ramadan** (c'est ce que dit
    la note horaire servie par le backend, et « Time in Morocco », en.wikipedia.org), donc
    l'iftar affiché est bien l'heure que le client connaît ;
  - l'**imsak ≈ lever − 80 min** — approximation assumée du fajr (l'écart lever↔aube varie
    de ~70 à ~95 min sous nos latitudes) ; seule l'heure d'**iftar**, calculée exactement,
    est affichée sur la puce (« Ramadan · iftar ≈ 18h31 »), pour que la modulation soit
    vérifiable par le client.
  Les **magnitudes sont inchangées** et restent des ordres de grandeur documentés : jour de
  jeûne ×0.65, suhoor ×2.5 sur les 2 h avant l'imsak, iftar ×1.8 sur l'heure de la rupture.
