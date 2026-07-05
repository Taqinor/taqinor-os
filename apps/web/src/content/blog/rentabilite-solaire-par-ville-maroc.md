---
title: "Rentabilité et retour sur investissement du solaire par ville marocaine"
description: "Payback 5–7 ans, production par ville et tarifs ONEE : tout ce qu'il faut savoir sur la rentabilité du solaire au Maroc."
pubDate: 2026-02-16
tags: ["rentabilité", "ROI", "production", "villes"]
author: "Reda Kasri"
ogSlug: "residentiel"
draft: false
---

Quand un client me demande si « le solaire est rentable chez lui », ma première question n'est pas le prix. C'est : dans quelle ville, et quelle est votre tranche ONEE ? Ces deux paramètres pèsent souvent plus que la marque des panneaux. Voici comment je raisonne, avec les chiffres que j'ai sous la main.

## Production solaire par ville : combien de kWh par kWc installé ?

Tout commence par le **rendement de site**, c'est-à-dire le nombre de kWh produits par kWc installé et par an (on l'appelle PVOUT). Il dépend de l'ensoleillement local, de l'inclinaison des panneaux et des pertes système : câblage, onduleur, poussière sur le verre.

Le tableau ci-dessous donne des fourchettes estimées, calculées à partir des données PVGIS, Global Solar Atlas et Solargis, avec un taux de perte système d'environ 14 % et une orientation plein sud, inclinaison optimale estimée pour chaque ville.

| Ville | PVOUT estimé (kWh/kWc/an) | Inclinaison optimale estimée (plein sud) |
|---|---|---|
| Tanger | ~1 550 – 1 650 | 31° |
| Casablanca | ~1 620 – 1 700 | 29° |
| Rabat-Salé | ~1 620 – 1 700 | 29° |
| Fès | ~1 650 – 1 750 | ~32° |
| Marrakech | **1 779** | 28° |
| Agadir | ~1 750 – 1 820 | 27° |
| Ouarzazate | ~1 850 – 1 950 | ~28–30° |

*Sources : PVGIS (Commission européenne) ; Global Solar Atlas (Banque mondiale / Solargis) ; MDPI Resources 2024 13(10):140 (Marrakech, PR 78 %). Les fourchettes des autres villes sont des estimations recalées sur le point Marrakech — non substituables à une simulation PVGIS à l'adresse exacte.*

> **Note de cohérence :** la page [/ensoleillement-maroc](/ensoleillement-maroc), tirée directement de notre extraction PVGIS TMY 2005–2020 (pertes système 14 %, PR 86 %), donne des valeurs plus basses pour ces mêmes villes (Marrakech ~1 650, Casablanca ~1 650, Agadir ~1 686 kWh/kWc/an) — un écart d'environ 8 % avec le point Marrakech ci-dessus. Ce n'est pas une contradiction : l'étude MDPI mesure le GTI (irradiation au plan des panneaux) et applique sa propre hypothèse de performance-ratio (PR 78 %), différente de celle de notre extraction PVGIS (PR 86 %) — deux méthodologies distinctes appliquées à la même ressource solaire ne donnent pas le même PVOUT final. Pour une estimation qui reflète exactement notre méthode de dimensionnement, référez-vous à /ensoleillement-maroc et à [notre méthodologie d'estimation](/methodologie-estimation).

**Repère national :** la bande PVOUT au Maroc se situe entre **1 600 et 1 900 kWh/kWc/an** (GSA). Les installateurs utilisent souvent la règle empirique **1 500–1 800 kWh/kWc/an selon la région**.

---

## Pourquoi le solaire est-il rentable au Maroc ? Le mécanisme des tarifs ONEE

### La grille tarifaire (vérifié par le fondateur, juin 2026)

Les tarifs ONEE/régie basse tension résidentiels en vigueur sont les suivants (TTC, grille `REGIE_TARIFF` — la même que celle utilisée par notre simulateur d'estimation) :

| Consommation mensuelle | Tarif (DH/kWh) | Mode de facturation |
|---|---|---|
| 0 – 100 kWh | 0,9010 | progressif |
| 101 – 150 kWh | 1,0732 | progressif |
| 151 – 210 kWh | 1,0732 | **sélectif** |
| 211 – 310 kWh | 1,1676 | **sélectif** |
| 311 – 510 kWh | 1,3817 | **sélectif** |
| > 510 kWh | 1,5958 | **sélectif** |

*Grille vérifiée par le fondateur (juin 2026), identique à celle qu'applique notre estimateur en ligne — voir [notre méthodologie d'estimation](/methodologie-estimation) et [l'ensoleillement par ville](/ensoleillement-maroc) pour la source live. Lydec/Casablanca et Redal/Rabat sont pour l'instant égalés à cette même grille (posture prudente en attendant une facture de référence propre à chaque régie) ; Amendis/Tanger suit la même structure de tranches. Une ancienne grille (0,90/1,07/1,18/1,45/1,66 DH/kWh, sourcée ~2015 via des agrégateurs comme kherba.com et calculateur.ma) circulait sur cet article — elle est **remplacée** par la grille ci-dessus, plus précise et alignée sur le simulateur.*

> **Note de fraîcheur :** ces tarifs sont stables depuis plusieurs années. Vérifiez sur [calculateur.ma](https://calculateur.ma) ou auprès de votre distributeur si vous lisez cet article après 2026.

### Le mécanisme « sélectif » : l'effet levier du solaire

C'est le point clé que beaucoup de consommateurs ignorent :

- En dessous de **150 kWh/mois**, la facturation est **progressive** : chaque tranche est facturée à son propre tarif.
- Au-dessus de **150 kWh/mois**, la facturation devient **« sélective »** : **toute la consommation du mois** est facturée au tarif de la tranche atteinte.

**Exemple concret :** un foyer qui consomme 250 kWh en juillet ne paie pas les 100 premiers kWh à 0,9010 DH puis les suivants à 1,0732… Il paie les 250 kWh *entiers* au tarif de la tranche 211–310 kWh, soit 1,1676 DH/kWh (une tolérance de 10 kWh par tranche atténue les dépassements de justesse).

Ce que le solaire supprime, c'est précisément ce tarif marginal élevé appliqué à la totalité de la facture. Prenez un foyer en tranche 311–510 kWh qui retire 200 kWh par mois du réseau grâce à ses panneaux : il économise ces 200 kWh au tarif *marginal* de 1,3817 DH, et non au tarif moyen apparent de son ancienne facture. C'est toute la raison pour laquelle la rentabilité grimpe chez les gros consommateurs, et c'est aussi ce que je vérifie en premier sur une facture avant de chiffrer quoi que ce soit.

---

## Retour sur investissement : 5 à 7 ans (consensus installateurs)

Le **payback résidentiel standard** est de **5 à 7 ans** — chiffre cohérent sur l'ensemble des sources installateurs consultées (solaropeak.com, ecovolt.ma, electrosolarplus.ma, lechantier.ma).

**Ce qui influence le payback :**
- **Votre tranche tarifaire actuelle** : plus vous êtes en tranche haute (≥ 1,3817 DH/kWh), plus les économies annuelles sont grandes et le retour rapide.
- **Le coût de l'installation** : fourchette indicative 2026 de ~10 000 à 14 000 DH/kWc (matériel + pose, sources installateurs — non audité). Voir [notre guide des prix](/blog/prix-installation-solaire-maroc-2026).
- **Votre taux d'autoconsommation** : la [loi 82-21](/blog/loi-82-21-autoproduction-2026) organise l'autoproduction basse tension, mais aucun tarif de rachat résidentiel (BT) n'est publié à ce jour — l'ANRE n'a publié un tarif de rachat que pour le moyen/haut/très haute tension (0,18–0,21 DH/kWh), pas pour les maisons < 11 kW. Tant que ce tarif BT n'existe pas noir sur blanc, nous ne chiffrons **aucun revenu d'export** : la valeur réelle du solaire est dans la consommation immédiate, pas dans la revente d'un surplus non valorisé (voir [notre méthodologie d'estimation](/methodologie-estimation)).
- **La batterie** : ajouter un stockage prolonge le payback de **1 à 3 ans** mais augmente le taux d'autoconsommation du soir.

**Sur 30 ans**, après remboursement de l'installation, chaque kWh produit est quasi-gratuit. Les panneaux modernes perdent environ 0,4 %/an de performance et l'ancien standard du marché (cellules PERC) les garantissait à ~80–85 % de leur capacité initiale à 25 ans — les panneaux N-type que nous installons vont au-delà : garantie de performance **linéaire sur 30 ans**, avec **≥ 87,4 % de la puissance initiale à 30 ans** (soit ≥ 89,4 % à 25 ans).

---

## Simulez votre installation

Les chiffres ci-dessus sont des fourchettes de marché. Votre rentabilité réelle dépend de votre consommation, votre ville, la surface et l'orientation de votre toit. [Obtenez un devis personnalisé](/devis/mon-toit) pour une estimation précise.

---

*Tarifs ONEE/régie (grille `REGIE_TARIFF`) vérifiés par le fondateur, juin 2026. Rendements par ville : estimations PVGIS/Global Solar Atlas/Solargis recalées sur la mesure Marrakech 1 779 kWh/kWc/an (MDPI Resources 2024, PR 78 %) — cette étude de terrain utilise une hypothèse de performance-ratio différente de l'extraction PVGIS TMY propre à Taqinor (PR 86 %, voir [/ensoleillement-maroc](/ensoleillement-maroc)), ce qui explique l'écart d'environ 8 % avec le tableau de rendement du site : les deux chiffres ne se contredisent pas, ils appliquent des méthodologies différentes à la même ressource solaire. Payback 5–7 ans : consensus sources installateurs marocains 2026.*
