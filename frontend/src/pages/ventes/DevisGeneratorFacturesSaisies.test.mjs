// N1/N4 (audit apercu-issues) — deux symptômes d'une même cause : `monthly`
// démarre avec les valeurs D'EXEMPLE du simulateur (DEFAULT_MONTHLY_BILLS,
// solar.js) et rien ne distinguait jamais « exemple encore intact » de
// « vraie facture saisie ».
//
//  N1 — Un devis créé À LA MAIN sur /ventes/devis/nouveau (hors devis auto
//       d'un lead) n'avait AUCUN moyen d'alimenter
//       `etude_params.factures_mensuelles_reelles` : le champ n'était semé
//       QUE par le devis auto (autoQuote.js, bloc PACT10/QF-REAL). Sans lui,
//       le moteur PDF perd la facture "avant" reconstruite (page 1
//       économies). Correctif : à l'enregistrement, si l'utilisateur a
//       RÉELLEMENT saisi une facture (hiver/été ou détail mensuel — jamais
//       les valeurs d'exemple), on sème `factures_mensuelles_reelles` +
//       `conso_annuelle` dérivée (même patron que S1 dans autoQuote.js) ;
//       rien saisi → payload inchangé.
//  N4 — Le graphique écran affichait « Facture ONEE » avec ces mêmes valeurs
//       D'EXEMPLE comme si c'était un fait, dès qu'un nombre de panneaux
//       était entré (roi ne dépend PAS de facturesSaisies). Correctif : le
//       graphique est masqué (message explicite) tant qu'aucune facture
//       réelle n'a été saisie.
//
// Les deux partagent le MÊME drapeau `facturesSaisies` (une seule dérivation,
// jamais deux logiques qui pourraient diverger).
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules (React, Redux dispatch réel) : ce test lit donc le SOURCE,
// même patron que DevisGeneratorOrdreLignes.test.mjs — et importe solar.js
// (pur, sans React) pour valider la formule avec les VRAIES constantes.
//
// Run : node --test src/pages/ventes/DevisGeneratorFacturesSaisies.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { DEFAULT_MONTHLY_BILLS } from '../../features/ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

test('facturesSaisies est dérivé de monthly vs DEFAULT_MONTHLY_BILLS (une seule dérivation, partagée N1+N4)', () => {
  assert.match(DG,
    /const facturesSaisies = monthly\.some\(\s*\n\s*\(v, i\) => Number\(v\) !== DEFAULT_MONTHLY_BILLS\[i\]\)/)
  // DEFAULT_MONTHLY_BILLS est bien importé de solar.js (pas une copie locale).
  assert.match(DG, /DEFAULT_MONTHLY_BILLS,/)
})

test('la formule facturesSaisies, rejouée avec les VRAIES constantes solar.js : False sur les valeurs d\'exemple, True dès qu\'une seule diffère', () => {
  // Reproduit EXACTEMENT la formule verrouillée par le test précédent.
  const facturesSaisies = (monthly) => monthly.some((v, i) => Number(v) !== DEFAULT_MONTHLY_BILLS[i])

  // Rien saisi (état initial de useState(DEFAULT_MONTHLY_BILLS)).
  assert.equal(facturesSaisies(DEFAULT_MONTHLY_BILLS), false)
  // Un formulaire réel manipule des chaînes (event.target.value) : la
  // coercition Number() doit rester insensible au type.
  assert.equal(facturesSaisies(DEFAULT_MONTHLY_BILLS.map(String)), false)

  // Un seul mois retouché à la main suffit.
  const unMoisRetouche = DEFAULT_MONTHLY_BILLS.slice()
  unMoisRetouche[3] = '999'
  assert.equal(facturesSaisies(unMoisRetouche), true)

  // Hiver/été estimé (estimerMois) diverge presque toujours des exemples.
  const hiverEteReels = [820, 820, 820, 700, 700, 700, 700, 700, 820, 820, 820, 820]
  assert.equal(facturesSaisies(hiverEteReels), true)
})

test('N1 — handleSubmit sème factures_mensuelles_reelles UNIQUEMENT si facturesSaisies, jamais un changement de payload sinon', () => {
  const idx = DG.indexOf('if (facturesSaisies) {')
  assert.ok(idx > -1, 'bloc de seed N1 introuvable dans handleSubmit')
  const bloc = DG.slice(idx, idx + 900)
  assert.match(bloc, /const facturesReelles = monthly\.map\(v => parseFloat\(v\) \|\| 0\)/)
  assert.match(bloc, /factures_mensuelles_reelles:\s*facturesReelles,/)
  // conso_annuelle dérivée via kwhFromBill (même patron que S1/autoQuote.js),
  // jamais un chiffre supposé — et jamais si une source plus directe existe déjà.
  assert.match(bloc, /if \(etudeParams\.conso_annuelle == null\) \{/)
  assert.match(bloc, /kwhFromBill\(bill, distributeur\)\.kwhMensuel \|\| 0/)

  // Le bloc vit AVANT buildEtudeParamsChoice (qui doit voir conso_annuelle
  // déjà posé pour ne pas le perdre) et APRÈS la construction des etudeParams
  // par mode (industriel/commercial/agricole).
  const buildChoiceIdx = DG.indexOf('etudeParams = buildEtudeParamsChoice(etudeParams, {')
  assert.ok(buildChoiceIdx > idx, 'le seed N1 doit précéder buildEtudeParamsChoice')
})

test('N1 — kwhFromBill est bien importé (réutilisé, jamais réécrit) dans DevisGenerator.jsx', () => {
  assert.match(DG, /kwhFromBill,/)
})

test('N4 — le graphique « Facture ONEE » est masqué (message explicite) tant que facturesSaisies est faux', () => {
  const chartTitleIdx = DG.indexOf('<div className="gen-chart-title">Économies mensuelles estimées')
  assert.ok(chartTitleIdx > -1, 'titre du graphique introuvable')
  const bloc = DG.slice(chartTitleIdx, chartTitleIdx + 2600)
  assert.match(bloc, /\{facturesSaisies \? \(/)
  assert.match(bloc, /<ComposedChart data=\{chartData\}>/)
  assert.match(bloc, /name="Facture ONEE \(MAD\)"/)
  // La branche "rien saisi" ne rend JAMAIS le graphique : un message textuel,
  // jamais des barres avec des valeurs par défaut qui se présenteraient comme
  // un fait.
  assert.match(bloc, /data-testid="chart-no-bills"/)
  // La branche "rien saisi" est bien le ELSE du ternaire facturesSaisies (pas
  // un second graphique caché juste à côté) : `) : (` précède immédiatement
  // le paragraphe, et le paragraphe lui-même ne mentionne aucun graphique.
  const ternaryElseIdx = bloc.indexOf(') : (')
  const noBillsIdx = bloc.indexOf('data-testid="chart-no-bills"')
  assert.ok(ternaryElseIdx > -1 && ternaryElseIdx < noBillsIdx,
    'le message "no-bills" doit vivre dans la branche ELSE du ternaire facturesSaisies')
  const paragraphBloc = bloc.slice(noBillsIdx, noBillsIdx + 300)
  assert.doesNotMatch(paragraphBloc, /ComposedChart/)
})
