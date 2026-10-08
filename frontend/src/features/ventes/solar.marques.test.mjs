// PVMRQ (fondateur 18/08/2026) — marque préférée par rôle de composition
// automatique (`ParametresGammes.marques`, apps/ventes/models.py), miroir
// frontend dans `autoFillLines` (solar.js). Verrouille
// les quatre garanties du contrat :
//   1. une marque épinglée GAGNE TOUJOURS (même quand une autre marque est
//      moins chère ou préférée par un tie-break existant, ex. « canadien ») ;
//   2. zéro correspondance en stock ⇒ zéro produit sur cette ligne — JAMAIS
//      un repli silencieux sur une autre marque — et `marquesManquantes`
//      consigne { role, marque } ;
//   3. la substitution « wattage le plus proche » ne joue plus que DANS le
//      vivier de la marque retenue ;
//   4. sans marque épinglée (`marques` absent/vide) : sortie BYTE-IDENTIQUE
//      au comportement historique (regression-lock).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  estimerMois,
  DAY_USAGE_DEFAULTS, KWH_PRICE, EFFICIENCY,
  consoAnnuelleDepuisFactures,
} from './solar.js'

const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
const P = (nom, ttc, marque) => ({
  id: ++_id, nom, prix_vente: ht(ttc), ...(marque ? { marque } : {}),
})

// Même catalogue que solar.test.mjs (SEEDED) — utilisé tel quel pour le
// verrou de régression « sans marque épinglée » ci-dessous.
const SEEDED = [
  P('Onduleur réseau Huawei 5kW Monophasé', 14000),
  P('Onduleur réseau Huawei 10kW Monophasé', 18000),
  P('Onduleur réseau Huawei 10kW Triphasé', 20000),
  P('Onduleur réseau Huawei 12kW Monophasé', 20000),
  P('Onduleur réseau Huawei 15kW Triphasé', 23000),
  P('Onduleur réseau Huawei 20kW Triphasé', 28000),
  P('Onduleur réseau Huawei 25kW Triphasé', 35000),
  P('Onduleur réseau Huawei 50kW Triphasé', 55000),
  P('Onduleur réseau Huawei 100kW Triphasé', 78000),
  P('Onduleur réseau Huawei 150kW Triphasé', 123000),
  P('Onduleur hybride Deye 5kW Monophasé', 17000),
  P('Onduleur hybride Deye 10kW Monophasé', 28000),
  P('Onduleur hybride Deye 10kW Triphasé', 28000),
  P('Onduleur hybride Deye 15kW Triphasé', 36000),
  P('Onduleur hybride Deye 20kW Triphasé', 48000),
  P('Panneau Canadien Solar 710W', 1400),
  P('Panneau Jinko 710W', 1400),
  P('Batterie Dyness 5 kWh', 17000),
  P('Batterie Dyness 10 kWh', 30000),
  P('Batterie Lithium 5 kWh', 15500),
  P('Batterie Gel 2.2 kWh', 5000),
  P('Structures acier', 500),
  P('Structures aluminium', 850),
  P('Socles', 80),
  P('Smart Meter', 1800),
  P('Wifi Dongle', 1200),
  P('Accessoires', 2000),
  P('Tableau De Protection AC/DC', 2000),
  P('Installation', 4800),
  P('Transport', 1000),
  P('Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 5000),
]

// ADEV69 — second composeur supprimé (D-QJR5-9) : la composition vit au serveur (apps/ventes/domain/composition.py, testée côté backend).
// Tests retirés (ils ne protégeaient QUE `autoFillLines`) :
//   · PVMRQ — sans marque épinglée, sortie BYTE-IDENTIQUE au comportement historique
//   · PVMRQ — marque épinglée GAGNE même sur le tie-break historique « canadien »
//   · PVMRQ — marque épinglée introuvable : AUCUN produit sur la ligne, jamais un repli, et marquesManquantes la consigne
//   · PVMRQ — onduleur : la marque épinglée gagne, une autre marque du même rôle n\
//   · PVMRQ — wattage le plus proche : substitution CONFINÉE au vivier de la marque épinglée
//   · PVMRQ — batterie : marque épinglée introuvable au vivier électriquement compatible
