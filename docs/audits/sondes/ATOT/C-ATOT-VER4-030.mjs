// C-ATOT-VER4-030 — vérifie ATOT (04/11, lot 4) : ATOT24 « l'aperçu ×N suit la chaîne du rail ».
// Rejeu PUR node des fonctions front d'origin/main 64c9c7317 (extraites par `git archive origin/main
// frontend/src/features/ventes frontend/src/lib`), aucune pile, aucune base.
// Lancer : node C-ATOT-VER4-030.mjs file:///<racine extraite>/frontend/src/
//
// Mécanisme : le rail (`DevisGenerator.jsx:924`) appelle `optionTotalsTTC(lines, pct, {scenario, produits, montee})`
// — AGNR36 : chaque ligne est classée sur désignation + nom du produit lié. L'aperçu ×N
// (`calc/totaux.js::multiPropertyPreviewTTC`, l.268) rappelle `optionTotalsTTC(lines, pct, {scenario, montee})`
// SANS `produits` : une désignation retouchée (« Onduleur Deye 5kW (garantie 10 ans) », « Stockage Dyness 5 kWh »)
// est classée sur la désignation seule. Les lignes de l'écran ne portent pas `produit_nom` (grep DevisGenerator : 0).
// Attendu (Then d'ATOT24) : aperçu.totalUnitaire = total du rail pour l'option effective ; totalMulti = N × rail.
const R = process.argv[2]
const { optionTotalsTTC, multiPropertyPreviewTTC } = await import(R + 'features/ventes/calc/totaux.js')

const produits = [
  { id: 1, nom: 'Panneau Longi 610W' },
  { id: 2, nom: 'Onduleur hybride Deye 5kW' },
  { id: 3, nom: 'Batterie Dyness 5 kWh' },
  { id: 4, nom: 'Structure aluminium' },
]
// Désignations retouchées à la main (cas AGNR36 / DEV-DEMO-0003), produits liés inchangés.
const lines = [
  { produit: 1, designation: 'Panneau Longi 610W', quantite: 10, prix_unit_ttc: 1481, taux_tva: 10 },
  { produit: 2, designation: 'Onduleur Deye 5kW (garantie 10 ans)', quantite: 1, prix_unit_ttc: 15000, taux_tva: 20 },
  { produit: 3, designation: 'Stockage Dyness 5 kWh', quantite: 1, prix_unit_ttc: 20000, taux_tva: 20 },
  { produit: 4, designation: 'Structure aluminium', quantite: 1, prix_unit_ttc: 4000, taux_tva: 20 },
]
const N = 3
const out = {}
for (const [scenario, option] of [['Sans batterie', 'sans'], ['Avec batterie', 'avec']]) {
  const rail = optionTotalsTTC(lines, 0, { scenario, produits, montee: true })
  const railOption = option === 'avec' ? rail.totalAvec : rail.totalSans
  const apercu = multiPropertyPreviewTTC(lines, { nombreProprietes: N, discountPct: 0, scenario, option, montee: true })
  out[scenario] = {
    rail_sans: rail.totalSans, rail_avec: rail.totalAvec, rail_option: railOption,
    attendu_xN: Math.round(railOption * 100) * N / 100,
    apercu_unitaire: apercu.totalUnitaire, apercu_xN: apercu.totalMulti,
    ecart_xN: Math.round((apercu.totalMulti - railOption * N) * 100) / 100,
  }
}
const repro = Object.values(out).some(o => o.ecart_xN !== 0)
console.log(JSON.stringify({ verdict: repro ? 'REPRO' : 'NON-REPRO', N, out }, null, 1))
