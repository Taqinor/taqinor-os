// QJR89 — tests des quatre modules de stratégie de marché. `node --test`
// uniquement (les modules n'importent que `solar.js` et `valeur.js`, sans
// node_modules).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as residentiel from './residentiel.js'
import * as industriel from './industriel.js'
import * as commercial from './commercial.js'
import * as agricole from './agricole.js'
import { unwrap, saisie, moteur, apercu, PUCE_APERCU } from '../valeur.js'

const MARCHES = { residentiel, industriel, commercial, agricole }

// ── L'interface UNIQUE ───────────────────────────────────────────────────────

test('les quatre modules exposent la MÊME interface', () => {
  for (const [nom, m] of Object.entries(MARCHES)) {
    assert.equal(m.cle, nom, `${nom}.cle`)
    assert.ok('defautScenario' in m, `${nom}.defautScenario`)
    assert.ok(Array.isArray(m.champsRequis), `${nom}.champsRequis`)
    for (const fn of ['dimensionner', 'composer', 'etudePersistee']) {
      assert.equal(typeof m[fn], 'function', `${nom}.${fn}`)
    }
    assert.equal(typeof m.default, 'object', `${nom}.default`)
  }
})

test('les scénarios par défaut sont ceux du contrat du moteur PDF', () => {
  assert.equal(residentiel.defautScenario, 'Les deux (Sans + Avec)')
  assert.equal(industriel.defautScenario, 'Sans batterie')
  assert.equal(commercial.defautScenario, 'Sans batterie')
  assert.equal(agricole.defautScenario, null)   // pompage : jamais de scénario
})

// ── RÉSIDENTIEL : structurellement incapable d'atteindre un producteur ───────

test('residentiel.dimensionner rend { mode: "serveur" } et RIEN d’autre', () => {
  const r = residentiel.dimensionner({ kwc: 12, factureHiver: '3000' },
    { computeAutoSizing: () => { throw new Error('jamais appelé') } })
  assert.deepEqual({ ...r }, { mode: 'serveur' })
  assert.deepEqual(Object.keys(r), ['mode'])
  // Aucune entrée ne peut le faire chiffrer autre chose.
  assert.deepEqual({ ...residentiel.dimensionner() }, { mode: 'serveur' })
  assert.deepEqual({ ...residentiel.dimensionner({}, {}) }, { mode: 'serveur' })
})

test('STRUCTUREL : residentiel.js n’importe AUCUN producteur local', () => {
  const src = readFileSync(new URL('./residentiel.js', import.meta.url), 'utf8')
  const imports = [...src.matchAll(/^import\s[^\n]*?from\s+'([^']+)'/gm)].map(m => m[1])
  // Un seul import autorisé : la primitive de la valeur signée (elle-même sans import).
  assert.deepEqual(imports, ['../valeur.js'])
  // Et aucune mention d'un producteur de chiffres, même en commentaire de code.
  for (const producteur of ['solar.js', 'computeAutoSizing', 'estimerPanneaux',
    'optimalKwcByPayback', 'autoFillLines', 'computeROI', 'estimerKwcDepuisFacture',
    'computeEtudeIndustrielle', 'pompageSelection']) {
    assert.equal(src.includes(`${producteur}(`), false,
      `residentiel.js APPELLE ${producteur} — le chemin résidentiel doit rester serveur`)
  }
})

test('residentiel.composer décrit le corps du dry-run SERVEUR, ne compose rien', () => {
  const c = residentiel.composer({ kwc: '8.52', panelW: '710', structure: 'acier' })
  assert.equal(c.mode, 'serveur')
  assert.deepEqual({ ...c.corps }, {
    kwc: 8.52, panel_watt: 710, structure_type: 'acier',
    scenario: 'Les deux (Sans + Avec)',
  })
  assert.equal('lignes' in c, false)   // aucune ligne produite ici
})

test('residentiel.etudePersistee : rien tant que le SERVEUR n’a pas chiffré', () => {
  const vide = residentiel.etudePersistee({})
  assert.equal(unwrap(vide).valeur, null)
  assert.match(unwrap(vide).motif, /moteur horaire/)
  // Une étude d'APERÇU local n'est jamais promue en étude persistée.
  const local = residentiel.etudePersistee({ etudeServeur: apercu({ economies: 1 }) })
  assert.equal(unwrap(local).valeur, null)
  // Seule l'étude SERVEUR passe.
  const srv = residentiel.etudePersistee({ etudeServeur: moteur({ economies_annuelles: 12000 }) })
  assert.deepEqual(unwrap(srv).valeur, { economies_annuelles: 12000 })
  assert.equal(unwrap(srv).source, 'moteur')
  assert.equal(unwrap(srv).puce, null)
})

// ── INDUSTRIEL / COMMERCIAL : QJR34 rendu STRUCTUREL ─────────────────────────

const ETAT_CI = {
  kwc: 100, totalTtc: 900000, dayUsagePct: 80,
  categorieCommerciale: 'hotel',
}

test('etudePersistee rend absent("aucune consommation saisie") sans entrée SIGNÉE', () => {
  for (const m of [industriel, commercial]) {
    // aucune consommation
    assert.equal(unwrap(m.etudePersistee(ETAT_CI)).motif, 'aucune consommation saisie')
    // une consommation NON signée (nombre nu) ne passe pas
    assert.equal(unwrap(m.etudePersistee({ ...ETAT_CI, consommation: 12000 })).motif,
      'aucune consommation saisie')
    // signée, mais pas par une SAISIE (dérivée d'un aperçu local)
    assert.equal(unwrap(m.etudePersistee({ ...ETAT_CI, consommation: apercu(12000) })).motif,
      'aucune consommation saisie')
    // signée serveur : ce n'est pas la consommation SAISIE du client non plus
    assert.equal(unwrap(m.etudePersistee({ ...ETAT_CI, consommation: moteur(12000) })).motif,
      'aucune consommation saisie')
    // signée saisie mais vide
    assert.equal(unwrap(m.etudePersistee({ ...ETAT_CI, consommation: saisie('') })).motif,
      'aucune consommation saisie')
  }
})

test('avec une consommation SAISIE, l’étude sort SIGNÉE « apercu » (étiquetée)', () => {
  const etat = { ...ETAT_CI, consommation: saisie('12000') }
  for (const m of [industriel, commercial]) {
    const r = unwrap(m.etudePersistee(etat))
    assert.equal(r.source, 'apercu')
    assert.equal(r.puce, PUCE_APERCU)     // « estimation d'exemple », toujours
    assert.equal(r.valeur.kwc, 100)
    assert.ok(r.valeur.production_annuelle > 0)
    assert.ok(r.valeur.economies_annuelles > 0)
  }
})

test('sans kWc, aucune étude n’est fabriquée', () => {
  const r = unwrap(industriel.etudePersistee({ ...ETAT_CI, kwc: 0, consommation: saisie('12000') }))
  assert.equal(r.valeur, null)
  assert.match(r.motif, /nombre de panneaux/)
})

test('QX44 : à facture égale, l’étude COMMERCIALE diffère de l’industrielle', () => {
  const etat = { ...ETAT_CI, consommation: saisie('12000'), categorieCommerciale: 'hotel' }
  const ind = unwrap(industriel.etudePersistee(etat)).valeur
  const com = unwrap(commercial.etudePersistee(etat)).valeur
  assert.notEqual(ind.taux_autoconso, com.taux_autoconso)   // 80 % vs archétype hôtel
  assert.ok(com.economies_annuelles < ind.economies_annuelles)
})

test('industriel/commercial : aucun moteur SERVEUR, la raison est toujours dite', () => {
  for (const m of [industriel, commercial]) {
    const d = m.dimensionner({ factureHiver: '3000' }, { computeAutoSizing: () => null })
    assert.equal(d.mode, 'local')
    assert.match(d.raison, new RegExp(m.cle))
    assert.equal(d.sizing, null)          // rien de chiffrable → RIEN, jamais un défaut
    const c = m.composer({ kwc: 0 }, {})
    assert.equal(c.mode, 'local')
    assert.match(c.raison, new RegExp(m.cle))
    assert.equal(c.lignes, null)
  }
})

test('le balayage local n’est retenu que s’il chiffre vraiment des panneaux', () => {
  const bon = industriel.dimensionner({ factureHiver: '3000' },
    { computeAutoSizing: () => ({ nbPanneaux: 30, kwcOptimal: 21.3 }) })
  assert.deepEqual(bon.sizing, { nbPanneaux: 30, kwcOptimal: 21.3 })
  const zero = industriel.dimensionner({ factureHiver: '900' },
    { computeAutoSizing: () => ({ nbPanneaux: 0 }) })
  assert.equal(zero.sizing, null)
})

// ── AGRICOLE : la moitié pompage ─────────────────────────────────────────────

test('agricole.etudePersistee : absent tant qu’aucune pompe n’est chiffrable', () => {
  const r = unwrap(agricole.etudePersistee({}, { produits: [] }))
  assert.equal(r.valeur, null)
  assert.equal(r.motif, agricole.MOTIF_SANS_POMPE)
})

test('agricole : pompe par CV — étude signée « apercu », SANS m³/jour inventé', () => {
  const r = unwrap(agricole.etudePersistee({ pompeCv: '3', pompeHeures: '7' },
    { produits: [] }))
  assert.equal(r.source, 'apercu')
  assert.equal(r.puce, PUCE_APERCU)
  assert.equal(r.valeur.pompe_cv, '3')
  assert.equal(r.valeur.mode_selection, 'cv')
  assert.ok(r.valeur.nb_panneaux >= 2)
  // Pompe SANS courbe : ni débit@HMT ni m³/jour — les clés sont ABSENTES.
  assert.equal('m3_jour' in r.valeur, false)
  assert.equal('debit_hmt_m3h' in r.valeur, false)
})

test('agricole : l’étude décrit EXACTEMENT la sélection déjà faite', () => {
  const d = agricole.dimensionner({ pompeCv: '3', pompeHeures: '7' }, { produits: [] })
  const r = unwrap(agricole.etudePersistee({ selection: d.selection }))
  assert.equal(r.valeur.pompe_kw, d.selection.kw)
  assert.equal(r.valeur.nb_panneaux, d.dims.nbPanneaux)
})

test('agricole.dimensionner/composer : local, avec sa raison, jamais de garniture', () => {
  const d = agricole.dimensionner({ pompeCv: '3' }, { produits: [] })
  assert.equal(d.mode, 'local')
  assert.match(d.raison, /agricole/)
  assert.equal(d.selection.mode, 'cv')
  assert.ok(d.dims.nbPanneaux >= 2)
  const c = agricole.composer({}, { produits: [] })
  assert.equal(c.mode, 'local')
  assert.deepEqual(c.lignes, [])            // rien de quotable
  assert.equal(c.motif, agricole.MOTIF_SANS_POMPE)
})

test('une composition pompage ne contient NI onduleur NI batterie', () => {
  // Catalogue minimal : le module ne doit jamais y ajouter batterie/onduleur.
  const c = agricole.composer({ pompeCv: '3', pompeAlim: 'tri' }, { produits: [] })
  for (const l of c.lignes) {
    const d = String(l.designation ?? '').toLowerCase()
    assert.equal(d.includes('batterie'), false)
    assert.equal(d.includes('onduleur'), false)
  }
})
