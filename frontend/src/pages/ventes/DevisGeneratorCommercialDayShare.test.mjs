// QJR575 — un devis commercial né du « Devis automatique » (part diurne 80 %,
// aucune catégorie) rouvert dans l'Édition complète puis enregistré SANS
// retouche ne doit plus réécrire taux_autoconso / économies / payback : la
// catégorie par défaut de l'écran n'est plus « hôtel » (55 %) mais la
// sentinelle « Non précisée » (80 %, persistée null). Et le balayage C&I de
// l'écran passe par LES MÊMES paramètres que celui du devis automatique
// (`parametresBalayageCI`, autoQuote.js) — jamais le défaut d'écran 'onee'.
//
// DevisGenerator.jsx (JSX) n'est pas importable sous `node --test` : lecture du
// SOURCE pour le câblage, solar.js pour les chiffres.
// Run : node --test src/pages/ventes/DevisGeneratorCommercialDayShare.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import {
  commercialDayShare, computeEtudeIndustrielle, DAY_USAGE_DEFAULTS,
} from '../../features/ventes/solar.js'
import { projeterEtudeMarche } from '../../features/ventes/quote/etudeMarcheBloc.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')
const PC = readFileSync(join(HERE, 'generator/PanneauCommercial.jsx'), 'utf8')
const CODE = DG.split(/\r?\n/).filter(l => !/^\s*\/\//.test(l)).join('\n')

test('la catégorie par défaut est la sentinelle « Non précisée », pas « hôtel »', () => {
  assert.match(CODE, /useState\(CATEGORIE_NON_PRECISEE\)/)
  assert.doesNotMatch(CODE, /useState\('hotel'\)/)
  assert.match(PC, /export const CATEGORIE_NON_PRECISEE = 'non_precisee'/)
  assert.match(PC, /Non précisée/)
})

test('la sentinelle vaut la part diurne du devis automatique (80 %) et se persiste null', () => {
  assert.equal(commercialDayShare('non_precisee'), DAY_USAGE_DEFAULTS.Commerciale)
  assert.match(CODE,
    /categorie: categorieCommerciale === CATEGORIE_NON_PRECISEE \? null : categorieCommerciale/)
})

test('rouvrir sans categorie_commerciale puis enregistrer : taux_autoconso et économies inchangés', () => {
  // L'étude que le devis automatique a persistée (part diurne 80 %)…
  const base = { kwp: 50, consoMensuelleKwh: 8000, totalTtc: 400000, kwhPrice: 1.2, efficiency: 0.8 }
  const auto = computeEtudeIndustrielle({ ...base, dayUsagePct: DAY_USAGE_DEFAULTS.Commerciale })
  // …et celle que l'écran rouvert recalcule avec SA catégorie par défaut.
  const ecran = computeEtudeIndustrielle({ ...base, dayUsagePct: commercialDayShare('non_precisee') })
  const bloc = projeterEtudeMarche('commercial', { etude: ecran, choix: {}, entrees: {}, categorie: null })
  assert.equal(bloc.taux_autoconso, auto.taux_autoconso)
  assert.equal(ecran.economies_annuelles, auto.economies_annuelles)
  assert.equal(bloc.payback, auto.payback)
  assert.equal(bloc.categorie_commerciale, null)
})

test('le balayage C&I de l\'écran passe par parametresBalayageCI (jamais utility: distributeur brut)', () => {
  const debut = CODE.indexOf('const computeAutoSizing = useCallback(')
  assert.ok(debut > -1)
  const bloc = CODE.slice(debut, CODE.indexOf('}, [modeInstallation', debut))
  assert.match(bloc, /parametresBalayageCI\(\{/)
  assert.doesNotMatch(bloc, /utility: distributeurBalayage/)
  assert.doesNotMatch(bloc, /DAY_USAGE_DEFAULTS\['Commerciale'\]/)
  // Distributeur DÉCLARÉ : celui que le vendeur a choisi, sinon celui du lead.
  assert.match(bloc, /distributeurChoisi \? distributeur : selectedLead\?\.distributeur/)
})
