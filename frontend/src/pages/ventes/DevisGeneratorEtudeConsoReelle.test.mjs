// QJR34 (audit L3 29/08/2026, origine QJF1 — règle fondateur zéro chiffre
// inventé) — l'étude industriel/commercial calculait `avgBill` depuis
// `monthly`, initialisé à DEFAULT_MONTHLY_BILLS (solar.js) : sans aucune
// facture réelle saisie ni consommation mensuelle tapée à la main,
// `consoKwhDerivee` pouvait être dérivé ENTIÈREMENT des valeurs D'EXEMPLE du
// simulateur, et donc le taux d'autoconsommation, les économies annuelles et
// le payback persistés dans etude_params + IMPRIMÉS sur le PDF client
// pouvaient décrire une facture fictive.
//
// `facturesSaisies` (:893) existe déjà et garde le graphique (N4) et
// `etude_params.factures_mensuelles_reelles` (N1) — mais ne gardait PAS ce
// calcul. Correctif : `avgBill` ne nourrit `consoKwhDerivee` QUE si
// `facturesSaisies` est vrai ; une saisie directe de `consoMensuelle` reste
// toujours prioritaire (elle EST une consommation réelle tapée à la main).
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules (React, Redux dispatch réel) : ce test lit donc le SOURCE,
// même patron que DevisGeneratorFacturesSaisies.test.mjs.
//
// Run : node --test src/pages/ventes/DevisGeneratorEtudeConsoReelle.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { DEFAULT_MONTHLY_BILLS } from '../../features/ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

test('QJR34 — consoKwhDerivee ne retombe sur avgBill que si facturesSaisies est vrai', () => {
  const idx = DG.indexOf('const consoKwhDerivee =')
  assert.ok(idx > -1, 'consoKwhDerivee introuvable')
  const bloc = DG.slice(idx, idx + 200)
  assert.match(bloc,
    /const consoKwhDerivee = \(parseFloat\(consoMensuelle\) \|\| 0\)\s*\n\s*\|\| \(facturesSaisies && avgBill > 0 \? Math\.round\(avgBill \/ quoteLogic\.kwhPrice\) : 0\)/,
    'consoKwhDerivee doit exiger facturesSaisies avant de retomber sur avgBill')
})

test('QJR34 — rejoué avec les VRAIES constantes solar.js : 0 sur les factures d\'exemple, dérivé seulement quand une vraie facture/consommation existe', () => {
  // Reproduit EXACTEMENT la formule verrouillée par le test précédent.
  const kwhPrice = 1.4
  const consoKwhDerivee = (consoMensuelle, monthly, facturesSaisies) => {
    const avgBill = monthly.reduce((s, v) => s + (parseFloat(v) || 0), 0) / 12
    return (parseFloat(consoMensuelle) || 0)
      || (facturesSaisies && avgBill > 0 ? Math.round(avgBill / kwhPrice) : 0)
  }
  const facturesSaisiesDe = (monthly) => monthly.some((v, i) => Number(v) !== DEFAULT_MONTHLY_BILLS[i])

  // État initial (montage) : monthly == DEFAULT_MONTHLY_BILLS, rien saisi.
  assert.equal(
    consoKwhDerivee('', DEFAULT_MONTHLY_BILLS, facturesSaisiesDe(DEFAULT_MONTHLY_BILLS)),
    0,
    'aucune facture réelle ni consommation saisie → 0 (jamais dérivé des exemples)')

  // Une vraie facture saisie (un seul mois retouché suffit à lever le drapeau).
  const facturesReelles = DEFAULT_MONTHLY_BILLS.slice()
  facturesReelles[3] = '2400'
  const avgReel = facturesReelles.reduce((s, v) => s + (parseFloat(v) || 0), 0) / 12
  assert.equal(
    consoKwhDerivee('', facturesReelles, facturesSaisiesDe(facturesReelles)),
    Math.round(avgReel / kwhPrice),
    'facturesSaisies vrai → dérivé de la vraie moyenne')

  // Consommation mensuelle tapée directement : toujours prioritaire, même
  // sans factures saisies.
  assert.equal(
    consoKwhDerivee('9500', DEFAULT_MONTHLY_BILLS, facturesSaisiesDe(DEFAULT_MONTHLY_BILLS)),
    9500,
    'la saisie directe de consoMensuelle prime toujours')
})

test('QJR34 — avis FR "Étude indisponible" rendu quand industriel/commercial sans etudeCI, jamais si etudeCI existe', () => {
  const idx = DG.indexOf('data-testid="etude-ci-indisponible"')
  assert.ok(idx > -1, 'le bloc d\'avis "étude indisponible" est introuvable')
  const bloc = DG.slice(idx - 350, idx + 250)
  assert.match(bloc,
    /\(modeInstallation === 'industriel' \|\| modeInstallation === 'commercial'\)\s*\n\s*&& !etudeCI/,
    'l\'avis doit être gardé par (industriel|commercial) && !etudeCI')
  assert.match(bloc, /Étude indisponible : saisissez la consommation ou les factures réelles\./)
  // Le bloc précédent (etudeCI &&) doit se refermer AVANT ce nouvel avis, pour
  // que les deux restent mutuellement exclusifs (jamais les deux affichés).
  const etudeCiBlockIdx = DG.indexOf('{etudeCI && (')
  assert.ok(etudeCiBlockIdx > -1 && etudeCiBlockIdx < idx,
    'le bloc etudeCI doit précéder l\'avis d\'indisponibilité')
})
