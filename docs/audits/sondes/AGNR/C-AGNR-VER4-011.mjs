// C-AGNR-VER4-011 — second lens (vérifie AGNR 04/11), rejeu PUR node des fonctions front à 4cd568403.
// Lancer : node C-AGNR-VER4-011.mjs file:///C:/dev/taqinor-os/frontend/src/   (checkout avec node_modules ;
// etatDevis.js / tarifs.js / useApercuEtude.js identiques à origin/main, vérifié par git diff).
// RÉSULTAT (04/11) : REPRO. hiver 500 / été 1200 → 12 'derivee', Mars tapé 900 :
//   facturesSaisies=true ; aperçu (useApercuEtude consoEcran, 12 cases) = 5979 kWh ;
//   corps entreesDeEtat = {factures_hiver_ete:{hiver_mad:500, ete_mad:1200, ete_differente:true}} — Mars 900 absent,
//   aucune conso_annuelle ; la même dérivation front sur hiver/été seuls donne 5779 kWh (écart 200 kWh/an).
//   Cas 2 (une case dérivée vidée → 'exemple') : facturesSaisies=false, corps = {} (hiver/été tapés non envoyés).
// C-AGNR-VER4-011 replay — pure frontend functions at origin/main 4cd568403 (worktree loop-audit-3de236).
const R = process.argv[2] || 'file:///C:/dev/taqinor-os/.claude/worktrees/loop-audit-3de236/frontend/src/'
const { entreesDeEtat } = await import(R + 'features/ventes/quote/etatDevis.js')
const { estimerMois } = await import(R + 'features/ventes/solar.js')
const { consoAnnuelleDepuisFactures } = await import(R + 'features/ventes/calc/tarifs.js')
const fHiver = '500', fEte = '1200'
const monthly = estimerMois(500, 1200).map(String)            // poserMoisDerives
const prov = Array(12).fill('derivee')
monthly[2] = '900'; prov[2] = 'tapee'                         // setMonth(2, '900')
// useApercuEtude.js:88-107 (pure part, realBillSaisi=false, mode factures)
const facturesSaisies = prov.every(p => p !== 'exemple')
const consoApercu = facturesSaisies ? consoAnnuelleDepuisFactures(monthly.map(v => parseFloat(v) || 0), 'onee') : null
const consoDerivee = consoAnnuelleDepuisFactures(estimerMois(500, 1200), 'onee')
const corps = entreesDeEtat({ monthly, provenanceMois: prov, facturesSaisies, fHiver, fEte,
  realBillSaisi: false, realBillMode: 'mad', consoAnnuelleReelle: 0, distributeur: 'onee',
  distributeurChoisi: false, consoStockee: null, bareme: null })
// second case: empty one derived month
const prov2 = Array(12).fill('derivee'); prov2[2] = 'exemple'
const m2 = estimerMois(500, 1200).map(String); m2[2] = ''
const fs2 = prov2.every(p => p !== 'exemple')
const corps2 = entreesDeEtat({ monthly: m2, provenanceMois: prov2, facturesSaisies: fs2, fHiver, fEte,
  realBillSaisi: false, realBillMode: 'mad', consoAnnuelleReelle: 0, distributeur: 'onee',
  distributeurChoisi: false, consoStockee: null, bareme: null })
console.log(JSON.stringify({ monthly, facturesSaisies, consoApercu, consoDeriveeSansMars900: consoDerivee,
  corps, marsEnvoye: JSON.stringify(corps).includes('900'), cas2: { facturesSaisies: fs2, corps: corps2 } }, null, 1))
