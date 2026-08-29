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

// ── N1 SURVIT À QJR66 — IL A SEULEMENT CHANGÉ DE CANAL ───────────────────────
// Le seed N1 vivait dans le bloc `etude_params` que `persisterDevis` posait EN
// BLOC dans le corps du devis — le mécanisme même qui EFFAÇAIT `gamme`,
// `etude_horaire`, `dimensionnement` et tout ce que les rafraîchisseurs
// serveur avaient écrit, à chaque sauvegarde du vendeur. QJR66 supprime CE
// MÉCANISME, pas la fonctionnalité : les 12 factures réelles partent
// désormais par l'endpoint de FUSION `PATCH /ventes/devis/<id>/etude-params/`
// (QJR62), où seules les clés envoyées bougent.
// ARBITRAGE ORCHESTRATEUR (29/08/2026) — « zéro perte » : ces entrées sont
// écrites pour TOUS les marchés, résidentiel COMPRIS. Un devis créé à la main
// (hors devis auto d'un lead) doit garder son moyen d'alimenter
// `factures_mensuelles_reelles`, sans quoi le moteur PDF reconstruit la
// facture « avant » depuis l'économie SUPPOSÉE — un proxy circulaire.
test('QJR66 — persisterDevis ne pose plus AUCUN etude_params dans le corps du devis (fin du remplacement en bloc)', () => {
  const start = DG.indexOf('const payload = {')
  assert.ok(start > -1, 'le payload de persisterDevis est introuvable')
  const bloc = DG.slice(start, DG.indexOf('}', DG.indexOf('prix_cible_kwc', start)))
  assert.doesNotMatch(bloc, /etude_params/,
    'le corps du devis ne doit plus porter etude_params (il écrasait tout le bloc)')
  assert.equal(DG.indexOf('buildEtudeParamsChoice('), -1,
    "buildEtudeParamsChoice n'a plus d'appelant sur ce chemin d'enregistrement")
  // Le bloc part par l'endpoint de FUSION, jamais par le corps du devis.
  assert.match(DG, /await ventesApi\.patchEtudeParams\(devisId, etudeMarche\)/)
})

// Les entrées RÉELLES de l'écran, tous marchés (`entreesReellesEcran`).
function entreesReelles() {
  const start = DG.indexOf('const entreesReellesEcran = (consoDejaConnue) => {')
  assert.ok(start > -1, 'entreesReellesEcran introuvable')
  const end = DG.indexOf('const blocEtudeMarche = () => {', start)
  assert.ok(end > start, 'la fin de entreesReellesEcran est introuvable')
  return DG.slice(start, end)
}

test('N1 — les 12 factures RÉELLES sont semées UNIQUEMENT si facturesSaisies (jamais les valeurs d\'exemple)', () => {
  const bloc = entreesReelles()
  assert.match(bloc, /if \(facturesSaisies\) \{/)
  assert.match(bloc,
    /entrees\.factures_mensuelles_reelles = monthly\.map\(v => parseFloat\(v\) \|\| 0\)/)
  // conso_annuelle dérivée via kwhFromBill (même patron que S1/autoQuote.js),
  // jamais un chiffre supposé — et jamais si une source plus directe existe.
  assert.match(bloc, /kwhFromBill\(bill, distributeur\)\.kwhMensuel \|\| 0/)
  assert.match(bloc, /if \(conso == null && consoAnnuelleReelle > 0\)/)
})

test('N1 — aucune de ces entrées n\'est jamais envoyée à null (null SUPPRIME côté serveur, règle Z2)', () => {
  const bloc = entreesReelles()
  // Le bloc n'ASSIGNE jamais null à une clé d'entrée : une clé inconnue de
  // l'écran est ABSENTE du corps, donc laissée intacte par la fusion — sinon
  // ré-enregistrer un devis auto effacerait les factures qu'il avait semées.
  assert.ok(!/entrees\.\w+ = null/.test(bloc),
    'une entrée envoyée à null supprimerait la donnée du serveur')
  assert.match(bloc, /if \(conso != null\) \{/)
})

test('QJR66 — l\'écran écrit les entrées réelles pour TOUS les marchés, et la sous-clé d\'étude de SON marché', () => {
  const start = DG.indexOf('const blocEtudeMarche = () => {')
  assert.ok(start > -1, 'blocEtudeMarche introuvable')
  const bloc = DG.slice(start, DG.indexOf('const persisterDevis', start))
  // Les trois branches de marché fusionnent les entrées réelles.
  assert.equal((bloc.match(/entreesReellesEcran\(/g) || []).length, 3,
    'les trois marchés doivent tous fusionner les entrées réelles de l\'écran')
  // Résidentiel : les entrées réelles SEULES — et rien du tout si rien tapé.
  assert.match(bloc, /Object\.keys\(entrees\)\.length \? entrees : null/)
  // Industriel / commercial : les cinq dérivées du marché (+ la catégorie).
  for (const cle of ['taux_autoconso', 'taux_couverture', 'payback',
                     'injection_kwh_an', 'injection_dh_an',
                     'categorie_commerciale']) {
    assert.ok(bloc.includes(cle), `clé industriel/commercial manquante : ${cle}`)
  }
  // Agricole : le bloc pompage du schéma.
  for (const cle of ['pompe_cv', 'pompe_kw', 'hmt_m', 'debit_hmt_m3h',
                     'm3_jour', 'champ_kwc', 'irrigation_method']) {
    assert.ok(bloc.includes(cle), `clé agricole manquante : ${cle}`)
  }
  // Aucune clé DÉRIVÉE dont l'écran n'est PAS propriétaire (le serveur les
  // calcule ; le schéma les refuserait en 400 — on ne les envoie même pas).
  for (const interdite of ['puissance_kwc', 'production_annuelle',
                           'economies_annuelles', 'etude_horaire',
                           'dimensionnement', 'profils_comparatifs']) {
    assert.ok(!bloc.includes(interdite),
      `clé dérivée non-propriétaire envoyée par l'écran : ${interdite}`)
  }
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
