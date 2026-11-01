// SONDE = {constat: "C-AGNR-VER-004", sha: "5093a9913",
//   attendu: "150 MAD/mois ONEE enregistré 1 282 kWh/an ⇒ rouvert, la « Consommation annuelle dérivée » (et la conso de l'aperçu) = 1 282"}
// Sonde Node (fonctions pures). Reproduit la formule de useApercuEtude.js::consoAnnuelleReelle (mode kWh) :
// Math.round(parseFloat(realBillKwh) * 12). Sortie 0 = REPRO (réaffiché ≠ enregistré), 1 = non reproduit.
import { devisVersEtat } from '../../../../frontend/src/features/ventes/quote/etatDevis.js'
import { consoAnnuelleDepuisFactures } from '../../../../frontend/src/features/ventes/calc/tarifs.js'

let repro = false
for (const mad of [150, 800, 1500]) {
  const enregistre = consoAnnuelleDepuisFactures(Array(12).fill(mad), 'onee')
  const etat = devisVersEtat({ id: 1, mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
    lignes: [], etude_params: { conso_annuelle: enregistre, distributeur: 'onee' } })
  const reaffiche = Math.round((parseFloat(etat.realBillKwh) || 0) * 12)
  console.log(`${mad} MAD : enregistré ${enregistre}, rouvert ${reaffiche} (mode ${etat.realBillMode})`)
  if (reaffiche !== enregistre) repro = true
}
console.log(`verdict : ${repro ? 'REPRO' : 'NON REPRODUIT'}`)
process.exit(repro ? 0 : 1)
