// N1/N4 (audit apercu-issues) — deux symptômes d'une même cause : les factures
// mensuelles de l'écran démarrent avec les valeurs D'EXEMPLE du simulateur
// (`DEFAULT_MONTHLY_BILLS`, solar.js) et rien ne distinguait « exemple encore
// intact » de « vraie facture saisie ».
//
//  N1 — un devis créé À LA MAIN n'avait aucun moyen d'alimenter
//       `etude_params.factures_mensuelles_reelles` ; sans lui le moteur PDF
//       reconstruit la facture « avant » depuis l'économie SUPPOSÉE — un
//       proxy circulaire.
//  N4 — le graphique « Facture ONEE » affichait ces valeurs D'EXEMPLE comme si
//       c'était un fait, dès qu'un nombre de panneaux était entré.
//
// QJR109 — CE FICHIER A CESSÉ DE LIRE LE SOURCE, et surtout de RÉÉCRIRE LA
// RÈGLE POUR LA TESTER. Il épinglait par regex la forme exacte de
// `const facturesSaisies = monthly.some(...)`, puis — pour « rejouer la
// formule » — la RECOPIAIT dans le test et testait cette copie : la
// production pouvait diverger sans que rien ne rougisse.
//
// LA GARDE PERMANENTE N'EST PLUS UN `if` DANS L'ÉCRAN. Depuis QJR86/QJR89 elle
// est un TYPE : une consommation voyage SIGNÉE de son origine
// (`saisie` = tapée par le vendeur, `apercu` = dérivée localement — un repère
// de vente, pas une mesure), et `etudeAutoconsommation` — la porte UNIQUE du
// calcul industriel/commercial — refuse tout ce qui n'est pas `saisie`. Les
// factures de DÉMONSTRATION, étant des valeurs d'aperçu, ne peuvent donc plus
// se faire persister : ce n'est plus un garde-fou qu'on peut oublier, c'est
// une porte qui ne s'ouvre pas. Ces modules sont purs : ils sont ici EXÉCUTÉS.
//
// CE QUI RESTE HORS DE PORTÉE D'UN TEST PUR (pas revendiqué ici) : le rendu du
// graphique et de son message de remplacement `data-testid="chart-no-bills"`,
// et le corps réellement envoyé par `persisterDevis` — deux comportements de
// composant React.
//
// Run : node --test src/pages/ventes/DevisGeneratorFacturesSaisies.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_MONTHLY_BILLS } from '../../features/ventes/solar.js'
import { apercu, saisie, moteur, absent, unwrap, PUCE_APERCU }
  from '../../features/ventes/quote/valeur.js'
import industriel, { MOTIF_SANS_CONSO }
  from '../../features/ventes/quote/marches/industriel.js'
import commercial from '../../features/ventes/quote/marches/commercial.js'
import residentiel from '../../features/ventes/quote/marches/residentiel.js'

/** Moyenne mensuelle des factures d'EXEMPLE — la valeur de démonstration. */
const MENSUEL_DEMO = DEFAULT_MONTHLY_BILLS.reduce((s, v) => s + Number(v), 0)
  / DEFAULT_MONTHLY_BILLS.length

const ETAT = { kwc: 100, totalTtc: 900000, dayUsagePct: 80,
               categorieCommerciale: 'hotel' }

// ── LA GARDE PERMANENTE : UN MENSUEL D'APERÇU NE SE PERSISTE JAMAIS ─────────

test('N1/N4 — un mensuel signé `apercu` (les factures de DÉMONSTRATION) fait rendre `absent`', () => {
  const etude = industriel.etudePersistee({
    ...ETAT, consommation: apercu(MENSUEL_DEMO) })
  const vu = unwrap(etude)
  assert.equal(vu.valeur, null, 'une facture de démonstration ne peut pas devenir une étude')
  assert.equal(vu.source, null)
  assert.equal(vu.motif, MOTIF_SANS_CONSO)
  assert.equal(MOTIF_SANS_CONSO, 'aucune consommation saisie')
})

test('la garde vaut aussi pour le marché COMMERCIAL — une seule porte, jamais deux règles', () => {
  const vu = unwrap(commercial.etudePersistee({
    ...ETAT, consommation: apercu(MENSUEL_DEMO) }))
  assert.equal(vu.valeur, null)
  assert.equal(vu.motif, MOTIF_SANS_CONSO)
})

test('la garde ne dépend pas de la VALEUR : même un mensuel d’aperçu généreux est refusé', () => {
  // C'est la différence entre un seuil et une PROVENANCE : ce qui est refusé,
  // c'est l'origine du chiffre, pas sa grandeur.
  for (const valeur of [MENSUEL_DEMO, 1, 999999, '4200']) {
    const vu = unwrap(industriel.etudePersistee({ ...ETAT, consommation: apercu(valeur) }))
    assert.equal(vu.valeur, null, `mensuel d’aperçu ${valeur}`)
  }
})

test('une consommation SIGNÉE MOTEUR n’est pas non plus une saisie du vendeur', () => {
  const vu = unwrap(industriel.etudePersistee({
    ...ETAT, consommation: moteur(4200) }))
  assert.equal(vu.valeur, null,
    'seule une consommation TAPÉE ouvre cette porte — le marché n’a pas de moteur serveur')
  assert.equal(vu.motif, MOTIF_SANS_CONSO)
})

test('une consommation NON SIGNÉE (nombre nu) est refusée — aucun chiffre nu ne se persiste', () => {
  for (const nu of [4200, '4200', null, undefined, {}, []]) {
    const vu = unwrap(industriel.etudePersistee({ ...ETAT, consommation: nu }))
    assert.equal(vu.valeur, null, `entrée nue ${JSON.stringify(nu)}`)
  }
})

test('un `absent` explicite reste absent (le motif du refus n’est pas remplacé par un chiffre)', () => {
  const vu = unwrap(industriel.etudePersistee({
    ...ETAT, consommation: absent('le client n’a pas fourni ses factures') }))
  assert.equal(vu.valeur, null)
  assert.equal(vu.motif, MOTIF_SANS_CONSO)
})

// ── CE QUI PASSE, ET COMMENT IL EST ÉTIQUETÉ ───────────────────────────────

test('N1 — une consommation RÉELLEMENT SAISIE ouvre la porte', () => {
  const vu = unwrap(industriel.etudePersistee({ ...ETAT, consommation: saisie(4200) }))
  assert.notEqual(vu.valeur, null, 'une vraie facture doit produire une étude')
  assert.equal(vu.motif, null)
})

test('…mais l’étude produite reste ÉTIQUETÉE « estimation d’exemple » (aucun moteur serveur ici)', () => {
  const vu = unwrap(industriel.etudePersistee({ ...ETAT, consommation: saisie(4200) }))
  assert.equal(vu.source, 'apercu')
  assert.equal(vu.puce, PUCE_APERCU)
  assert.equal(vu.puce, "estimation d'exemple")
})

test('une saisie à ZÉRO n’est pas une saisie (jamais une étude bâtie sur rien)', () => {
  for (const vide of [0, '0', '', 'abc']) {
    const vu = unwrap(industriel.etudePersistee({ ...ETAT, consommation: saisie(vide) }))
    assert.equal(vu.valeur, null, `saisie vide ${JSON.stringify(vide)}`)
    assert.equal(vu.motif, MOTIF_SANS_CONSO)
  }
})

test('sans kWc à étudier, le refus NOMME sa propre cause (jamais celle d’à côté)', () => {
  const vu = unwrap(industriel.etudePersistee({
    ...ETAT, kwc: 0, consommation: saisie(4200) }))
  assert.equal(vu.valeur, null)
  assert.match(vu.motif, /nombre de panneaux/)
  assert.notEqual(vu.motif, MOTIF_SANS_CONSO)
})

// ── LE MÊME PRINCIPE CÔTÉ RÉSIDENTIEL ──────────────────────────────────────

test('résidentiel — une étude d’APERÇU n’est jamais promue en étude persistée', () => {
  const vu = unwrap(residentiel.etudePersistee({
    etudeServeur: apercu({ economies: 1, factures: DEFAULT_MONTHLY_BILLS }) }))
  assert.equal(vu.valeur, null)
  assert.match(vu.motif, /moteur horaire/)
})

test('résidentiel — seule l’étude SERVEUR passe, et elle passe SANS puce', () => {
  const vu = unwrap(residentiel.etudePersistee({
    etudeServeur: moteur({ economies_annuelles: 12000 }) }))
  assert.deepEqual(vu.valeur, { economies_annuelles: 12000 })
  assert.equal(vu.source, 'moteur')
  assert.equal(vu.puce, null, 'un chiffre serveur est publiable tel quel')
})

test('résidentiel — sans étude du tout, le motif est FRANÇAIS et explicite', () => {
  const vu = unwrap(residentiel.etudePersistee({}))
  assert.equal(vu.valeur, null)
  assert.equal(typeof vu.motif, 'string')
  assert.notEqual(vu.motif.trim(), '')
})

// ── LES FACTURES D'EXEMPLE ELLES-MÊMES ─────────────────────────────────────

test('les factures d’EXEMPLE existent bien, et c’est précisément pour ça qu’il faut une garde', () => {
  assert.equal(Array.isArray(DEFAULT_MONTHLY_BILLS), true)
  assert.equal(DEFAULT_MONTHLY_BILLS.length, 12, 'douze mois')
  assert.equal(DEFAULT_MONTHLY_BILLS.every(v => Number(v) > 0), true,
    'des valeurs plausibles — c’est ce qui les rend dangereuses si elles fuitent')
  assert.ok(MENSUEL_DEMO > 0)
})

test('une valeur d’aperçu ne peut pas être RE-SIGNÉE en saisie pour contourner la garde', () => {
  // La primitive refuse de re-signer : on ne peut pas blanchir une valeur de
  // démonstration en la faisant passer pour une saisie.
  assert.throws(() => saisie(apercu(MENSUEL_DEMO)), TypeError)
  assert.throws(() => moteur(apercu(MENSUEL_DEMO)), TypeError)
  assert.throws(() => apercu(saisie(4200)), TypeError)
})

test('un `absent` sans motif est impossible : un vide sans explication est interdit', () => {
  assert.throws(() => absent(''), TypeError)
  assert.throws(() => absent(null), TypeError)
})

test('le déballeur REFUSE un nombre nu — c’est ce refus qui rend la règle exécutable', () => {
  assert.throws(() => unwrap(MENSUEL_DEMO), TypeError)
  assert.throws(() => unwrap(DEFAULT_MONTHLY_BILLS), TypeError)
})
