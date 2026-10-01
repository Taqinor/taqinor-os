// QJR575 — un devis commercial né du « Devis automatique » (part diurne 80 %,
// aucune catégorie) rouvert dans l'Édition complète puis enregistré SANS
// retouche ne doit plus réécrire taux_autoconso / économies / payback : la
// catégorie par défaut de l'écran n'est plus « hôtel » (55 %) mais la
// sentinelle « Non précisée » (80 %, persistée null). Et le balayage C&I de
// l'écran passe par LES MÊMES paramètres que celui du devis automatique
// (`parametresBalayageCI`, autoQuote.js) — jamais le défaut d'écran 'onee'.
//
// DevisGenerator.jsx / autoQuote.js ne sont pas importables sous `node --test` :
// ce fichier exécute les chiffres (solar.js, projeterEtudeMarche) ; le balayage
// parametresBalayageCI est exécuté par autoQuote.balayageCI.test.jsx (vitest).
// Run : node --test src/pages/ventes/DevisGeneratorCommercialDayShare.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  commercialDayShare, computeEtudeIndustrielle, DAY_USAGE_DEFAULTS,
} from '../../features/ventes/solar.js'
import { projeterEtudeMarche } from '../../features/ventes/quote/etudeMarcheBloc.js'


test('la sentinelle « Non précisée » (clé inconnue) vaut la part diurne du devis automatique (80 %)', () => {
  assert.equal(commercialDayShare('non_precisee'), DAY_USAGE_DEFAULTS.Commerciale)
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
