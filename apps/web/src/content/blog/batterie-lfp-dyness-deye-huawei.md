---
title: "Quelle batterie LFP choisir : la gamme Dyness, et Deye vs Huawei pour le secours"
description: "Gamme Dyness LFP, ≥6 000 cycles, 10 ans de garantie — et le vrai différenciateur secours entre Deye SG (≈4–10 ms) et Huawei SUN2000 (< 3 s)."
pubDate: 2026-04-27
tags: ["batterie", "LFP", "Dyness", "Deye", "Huawei"]
author: "Reda Kasri"
ogSlug: "equipement"
draft: false
theme: "Batteries"
---

Sur le terrain, le choix d'une batterie se joue rarement sur la capacité affichée. Il se joue sur deux détails qu'on oublie en showroom : comment la chimie vieillit sous la chaleur marocaine, et ce qui se passe exactement à l'instant où l'ONEE coupe le courant. Je passe sur ces deux points avec la gamme que j'installe le plus, Dyness, puis je tranche le débat onduleur entre Deye et Huawei.

## La gamme Dyness LFP

Toute la gamme Dyness est en chimie **LiFePO4 (LFP)**, devenue la référence du stockage résidentiel au Maroc : elle encaisse bien la chaleur, reste sûre (aucun dégagement d'oxygène en cas d'emballement) et dure nettement plus longtemps que le gel ou l'AGM.

Tous les modèles partagent le même socle : **≥ 6 000 cycles** et une **garantie 10 ans à 70 % de rétention de capacité**.

| Modèle | Capacité nominale | Particularité |
|---|---|---|
| **B4850** | 2,4 kWh | Entrée de gamme, 90 % de DoD, 0–55 °C |
| **PowerDepot H5B** | 5,12 kWh | Chauffage intégré, **−20 à +55 °C**, ≈ 95 % DoD |
| **Tower T7** | 7,10 kWh | Haute tension empilable, 95 % DoD |
| **Tower T10** | 10,66 kWh | Haute tension empilable, 95 % DoD |
| **Tower T14** | 14,21 kWh | Haute tension empilable, 95 % DoD |
| **PowerBrick** | 14,34 kWh | ≥ 8 000 cycles, rendement aller-retour **> 95 %**, 55 °C max |

Sur l'ensemble de la gamme, la chimie LFP offre un rendement aller-retour de l'ordre de **≈ 95 %** en conditions normales, le PowerBrick affichant **> 95 %** en datasheet.

---

## Le différenciateur secours : Deye SG-series vs Huawei SUN2000

Le critère souvent négligé dans le choix d'un onduleur hybride, c'est la **qualité du secours** — ce qui se passe exactement quand ONEE coupe le courant.

### Deye SG-series (SG03LP1 monophasé / SG04LP3 triphasé)

- Bascule **≈ 4–10 ms** — quasi-instantanée, **de type UPS**
- **Aucun boîtier supplémentaire** : le secours est intégré à l'onduleur
- Compatible **batterie LFP 48 V basse tension** (dont la gamme Dyness)
- **6 fenêtres TOU** configurables (charge/décharge par plage horaire)

Une coupure de ≈ 4–10 ms est imperceptible pour la quasi-totalité des équipements domestiques (ordinateurs, NAS, appareils médicaux courants). C'est ce que l'on désigne par le terme UPS (*Uninterruptible Power Supply*).

> Le délai de ≈ 4 ms est corroboré par des retours d'utilisateurs et forums spécialisés ; le PDF fabricant n'étant pas directement accessible, nous le citons avec "≈".

### Huawei SUN2000 + Backup Box (L1 monophasé / M1 triphasé)

- Bascule **< 3 s** — une coupure brève mais perceptible ; **pas UPS**
- Le secours nécessite un **Backup Box séparé** (B0 ou B1 selon la puissance)
- Technologie haute tension (≈ 350–980 V), batterie LUNA2000 HV
- Suivi de production en temps réel excellent, intégration soignée, TOU nocturne disponible

| Critère | Deye SG-series | Huawei SUN2000 + Backup Box |
|---|---|---|
| Délai de bascule | **≈ 4–10 ms (UPS)** | **< 3 s** (coupure brève) |
| Boîtier secours séparé | Non, intégré | Oui (Backup Box B0/B1) |
| Triphasé sans secours | Non (le SG04LP3 assure le secours) | **SUN2000 M0 : aucun secours** |
| Tension batterie | 48 V basse tension | Haute tension (LUNA2000) |
| Fenêtres TOU | **6** | Oui (nombre selon firmware) |

**Point d'attention Huawei :** le modèle **SUN2000 M0 (triphasé d'entrée de gamme) ne propose aucune fonction secours**, même avec une batterie branchée. Si le secours est votre priorité, vérifiez précisément le modèle commandé (L1 mono ou M1 tri avec Backup Box).

---

## Durée de vie LFP et effets de la chaleur

### Combien de temps dure une batterie LFP ?

- Durée de vie **calendaire : ≈ 10–15 ans** dans des conditions normales
- Les garanties fabricant ciblent typiquement 10 ans à 70 % de rétention
- À raison d'un cycle par jour, le budget cycles (4 000–6 000) représente ≈ 11–16 ans — c'est souvent le **vieillissement calendaire** qui limite en premier, pas le compteur de cycles

### L'ennemi numéro 1 : la chaleur

**+ 10 °C ≈ divise la durée de vie par deux** (règle d'ordre de grandeur, source : Battery University). Une batterie stockée à 45 °C vieillira deux fois plus vite qu'à 35 °C. Au Maroc, cela signifie :

- Installer la batterie dans un local **ombragé et ventilé** (cave, pièce technique, garage au nord)
- Éviter les pièces exposées au soleil ou sous toiture métallique non isolée
- Température optimale : **15–35 °C**

### Attention au froid : ne jamais charger une LFP sous 0 °C

En dessous de 0 °C, charger une cellule LFP provoque un **dépôt de lithium métallique** (lithium plating) qui endommage l'anode de façon permanente et réduit irrémédiablement la capacité.

En usage marocain, cela concerne principalement :
- Le **Haut Atlas** et les zones montagneuses (nuits d'hiver sous 0 °C)
- Les installations agricoles en altitude (pompage solaire)

Le **Dyness PowerDepot H5B** est équipé d'un **chauffage intégré** qui préchauffe les cellules avant la charge — une fonctionnalité concrètement utile dans ces contextes, pas un argument marketing.

---

## Comment je tranche, selon le cas

Voici la grille de décision que j'utilise en rendez-vous :

- Secours sans coupure perceptible indispensable (équipements médicaux, télétravail, congélateur) : **Deye SG-series** avec batterie Dyness basse tension.
- Priorité à un écosystème intégré et à un suivi de production en temps réel poussé, 3 secondes de coupure tolérées : **Huawei SUN2000 L1/M1 + LUNA2000 + Backup Box**.
- Petit système (entrée de gamme, maison secondaire) : Dyness **B4850** (2,4 kWh).
- Installation en montagne ou zone à gel hivernal : Dyness **PowerDepot H5B** (chauffage intégré, −20 °C).
- Capacité maximale dans un espace réduit : **PowerBrick** (14,34 kWh, ≥ 8 000 cycles).

Pour connaître la taille d'installation adaptée à votre consommation, consultez notre guide [Lithium ou gel — quelle chimie choisir ?](/guides/batterie-lithium-ou-gel) et notre article [Stocker ou revendre : quel arbitrage avec la loi 82-21 ?](/blog/batterie-stocker-ou-revendre-maroc).

Vous souhaitez un devis avec la configuration précise (batterie + onduleur + panneaux) ? Notre simulateur calcule la puissance recommandée à partir de votre facture ONEE. → **[Obtenir un diagnostic personnalisé](/devis/mon-toit)**
