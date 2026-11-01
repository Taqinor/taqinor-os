// SONDE = {constat: "C-AMOT-VER-005", sha: "d57c36964",
//   attendu: "devis remisé de 10 %, onduleur 24 000 TTC : le payback de l'écran du générateur égale roi_a du PDF (provision payée 21 600)"}
// Sonde Node (fonctions pures du front, sans DOM ni build) : `node docs/audits/sondes/AMOT/C-AMOT-VER-005.mjs`.
// L'écran (`pages/ventes/generator/hooks/useApercuEtude.js`) passe `inverterCostFromLines(...)` = prix TTC des lignes
// SANS la remise globale ; le serveur (`quote_engine/etude_chiffrage.py::_cout_onduleur_paye`, niveau de règles >= 3)
// provisionne le prix PAYÉ (remise déduite). Même moteur (`calc/roi.js::paybackMoteurHoraire`, miroir prouvé par AMOT72),
// seule la provision change. Sortie 0 = REPRO (paybacks différents), 1 = non reproduit.
import { paybackMoteurHoraire } from '../../../../frontend/src/features/ventes/calc/roi.js'

const total = 90000, eco = 7200, onduleurTtc = 24000, remise = 10
const ecran = paybackMoteurHoraire(total, eco, { stockage: true, rendementBatterie: 0.9, inverterReplaceCost: onduleurTtc })
const pdf = paybackMoteurHoraire(total, eco, { stockage: true, rendementBatterie: 0.9,
  inverterReplaceCost: onduleurTtc * (1 - remise / 100) })
const repro = Math.abs(ecran.paybackYears - pdf.paybackYears) >= 0.1
console.log(`écran : ${ecran.paybackYears} ans, gain net ${ecran.netGain} ; PDF (provision payée) : ${pdf.paybackYears} ans, gain net ${pdf.netGain}`)
console.log(`verdict : ${repro ? 'REPRO' : 'NON REPRODUIT'}`)
process.exit(repro ? 0 : 1)
