// QJR523 — un seul couple de mappeurs lignes serveur ⇄ écran.
// Exécuté en CI : node --test src/features/ventes/quote/lignesEcran.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import {
  lignesServeurVersEcran, lignesEcranVersPayload,
  baseLegaleManquante, erreursBaseLegaleServeur,
} from './lignesEcran.js'
import { documentContrat, exempleContrat } from '../../../test/fixtures/contractSamples.js'

const ICI = dirname(fileURLToPath(import.meta.url))

// Lignes serveur « générées » : le corps committé du contrat replace-lines
// (QJR504) enrichi des champs que le serveur sert en plus (id, groupe villa,
// rôle stocké), + une section intercalée.
function lignesServeur() {
  const base = documentContrat('ventes', 'devis_replace_lines_entete').corps.lignes
  return [
    { id: 11, ...base[0], groupe_index: 1, groupe_label: 'Villa A', role_devis: 'panneau' },
    { id: 12, type_ligne: 'section', designation: 'Stockage', ordre: 1,
      produit: null, quantite: '0', prix_unitaire: '0', taux_tva: '20.00' },
    { id: 13, ...base[1], ordre: 2, groupe_index: 0, groupe_label: '',
      role_devis: 'onduleur_offgrid' },
  ]
}

test('aller-retour serveur → écran → payload : chaque champ porté est préservé', () => {
  const serveur = lignesServeur()
  const payload = lignesEcranVersPayload(lignesServeurVersEcran(serveur, '20.00'),
    { multiMode: 'villas' })
  assert.equal(payload.length, 3)
  const [p0, sec, p1] = payload
  const [s0, , s1] = serveur
  for (const [p, s] of [[p0, s0], [p1, s1]]) {
    assert.equal(p.produit, s.produit)
    assert.equal(p.designation, s.designation)
    assert.equal(parseFloat(p.quantite), parseFloat(s.quantite))
    assert.equal(p.prix_unitaire, parseFloat(s.prix_unitaire).toFixed(2))
    assert.equal(parseFloat(p.taux_tva), parseFloat(s.taux_tva))
    assert.equal(p.optionnelle, s.optionnelle)
    assert.equal(p.type_ligne, 'produit')
    assert.equal(p.variante, s.variante)
    assert.equal(p.prix_manuel, s.prix_manuel)
    assert.equal(p.quantite_manuelle, s.quantite_manuelle)
    assert.equal(p.groupe_index, s.groupe_index)
    assert.equal(p.groupe_label, s.groupe_label)
    assert.equal(p.role_devis, s.role_devis)
    assert.equal(p.ligne_composee, s.ligne_composee)
  }
  assert.deepEqual(sec, { type_ligne: 'section', ordre: 1, designation: 'Stockage',
    ligne_composee: null })
  assert.deepEqual(payload.map(p => p.ordre), [0, 1, 2])
})

test('l’ordre serveur (ordre, id) est respecté à la réouverture', () => {
  const serveur = lignesServeur().reverse()
  const ecran = lignesServeurVersEcran(serveur, 20)
  assert.deepEqual(ecran.map(l => l.designation),
    ['Panneau Canadien Solar 710W', 'Stockage', 'Batterie Dyness 10 kWh'])
})

test('role_devis survit (le serveur ne re-devine plus le rôle)', () => {
  const ecran = lignesServeurVersEcran(lignesServeur(), 20)
  assert.equal(ecran[2].role_devis, 'onduleur_offgrid')
})

test('hors mode villas, les groupes partent à null (comportement historique)', () => {
  const payload = lignesEcranVersPayload(lignesServeurVersEcran(lignesServeur(), 20),
    { multiMode: 'none' })
  assert.equal(payload[0].groupe_index, null)
  assert.equal(payload[0].groupe_label, '')
})

test('modèle appliqué (produit_id / prix_unit_ht) passe par le même mappeur', () => {
  const [l] = lignesServeurVersEcran([
    { produit_id: 5, designation: 'X', prix_unit_ht: '100.00', taux_tva: 10 },
  ])
  assert.equal(l.produit, '5')
  assert.equal(l.quantite, '1')
  assert.equal(l.prix_unit_ttc, '110')
  assert.equal(l.taux_tva, '10')
})

test('lignes vides / sans produit / quantité nulle ne partent pas', () => {
  const payload = lignesEcranVersPayload([
    { produit: '', quantite: '2', prix_unit_ttc: '10', typeLigne: 'produit' },
    { produit: '3', quantite: '0', prix_unit_ttc: '10', typeLigne: 'produit' },
    { typeLigne: 'note', designation: '   ' },
  ])
  assert.deepEqual(payload, [])
})

test('garde de source : plus de mappeur inline dans DevisGenerator.jsx', () => {
  const src = readFileSync(join(ICI, '../../../pages/ventes/DevisGenerator.jsx'), 'utf8')
  assert.ok(!src.includes('ttcFromHt(l.prix_unitaire'),
    'conversion HT → TTC inline d’une ligne serveur : passer par lignesServeurVersEcran')
  assert.ok(!src.includes('ttcExactFromHt(l.prix_unitaire'),
    'conversion HT → TTC inline d’une ligne serveur : passer par lignesServeurVersEcran')
  assert.ok(!/prix_unitaire:\s*htFromTtc\(/.test(src),
    'payload de lignes inline : passer par lignesEcranVersPayload')
  // QJR658 — l'Édition complète passe par le module pur `etatDevis.js`, qui
  // COMPOSE ces deux mappeurs (lecture `?edit=` et écriture replace-lines).
  const etat = readFileSync(join(ICI, 'etatDevis.js'), 'utf8')
  assert.ok(src.includes('lignesServeurVersEcran(') && src.includes('etatVersEcritures('))
  assert.ok(etat.includes('lignesServeurVersEcran(') && etat.includes('lignesEcranVersPayload('))
})

test('QJR529 — la remise de ligne stockée survit à l’aller-retour (défaut « 0 »)', () => {
  const ecran = lignesServeurVersEcran([
    { id: 1, produit: 3, designation: 'Panneau 550W', quantite: '2',
      prix_unitaire: '1000.00', taux_tva: '10.00', remise: '10.00' },
    { id: 2, produit: 4, designation: 'Onduleur réseau', quantite: '1',
      prix_unitaire: '5000.00', taux_tva: '20.00' },
  ], 20)
  assert.equal(ecran[0].remise, '10')
  assert.equal(ecran[1].remise, '0')
  const payload = lignesEcranVersPayload(ecran)
  assert.equal(payload[0].remise, '10')
  assert.equal(payload[1].remise, '0')
})

test('QJR667 — le lot multi-sites de la ligne fait l’aller-retour (défaut null)', () => {
  const ecran = lignesServeurVersEcran([
    { id: 1, produit: 3, designation: 'Panneau 550W', quantite: '2',
      prix_unitaire: '1000.00', taux_tva: '20.00', lot: 31 },
    { id: 2, produit: 4, designation: 'Onduleur réseau', quantite: '1',
      prix_unitaire: '5000.00', taux_tva: '20.00' },
  ], 20)
  assert.equal(ecran[0].lot, 31)
  assert.equal(ecran[1].lot, null)
  const payload = lignesEcranVersPayload(ecran)
  assert.equal(payload[0].lot, 31)
  assert.equal(payload[1].lot, null)
})

// ERR-QJR570 (D-QJR5-4) — la PROVENANCE d'une ligne (composée par le moteur /
// ajoutée à la main) est PERSISTÉE (`LigneDevis.ligne_composee`) et fait
// l'aller-retour : sans elle, un produit ajouté à la main, enregistré puis
// rouvert, était pris pour une ligne composée et REMPLACÉ au recalcul suivant.
test('ERR-QJR570 — la provenance (composée / ajoutée à la main) fait l’aller-retour écran → payload → écran', () => {
  const serveur = [
    { id: 1, ordre: 0, produit: 3, designation: 'Panneau 550W', quantite: '2',
      prix_unitaire: '1000.00', taux_tva: '20.00', ligne_composee: true },
    { id: 2, ordre: 1, produit: 4, designation: 'Onduleur réseau', quantite: '1',
      prix_unitaire: '5000.00', taux_tva: '20.00', ligne_composee: false },
    { id: 3, ordre: 2, type_ligne: 'section', designation: 'Options',
      produit: null, quantite: '0', prix_unitaire: '0', ligne_composee: null },
  ]
  const ecran = lignesServeurVersEcran(serveur, 20)
  assert.deepEqual(ecran.map(l => l.compose), [true, false, false])
  const payload = lignesEcranVersPayload(ecran)
  assert.deepEqual(payload.map(p => p.ligne_composee), [true, false, null])
  // Le serveur rend ce qu'il a reçu : la réouverture retrouve la provenance.
  const relu = lignesServeurVersEcran(payload.map((p, i) => ({ id: i + 1, ...p })), 20)
  assert.deepEqual(relu.map(l => l.compose), [true, false, false])
})

test('ERR-QJR570 — une ligne « Ajouter une ligne » (compose absent) part en ligne_composee:false', () => {
  const [p] = lignesEcranVersPayload([
    { produit: '4', designation: 'Onduleur réseau', quantite: '1',
      prix_unit_ttc: '6000', taux_tva: '20', typeLigne: 'produit' },
  ])
  assert.equal(p.ligne_composee, false)
})

test('ERR-QJR570 — le contrat replace-lines porte ligne_composee sur ses lignes', () => {
  const lignes = documentContrat('ventes', 'devis_replace_lines_entete').corps.lignes
  assert.deepEqual(lignes.map(l => l.ligne_composee), [true, false])
})

// ── AGR218 — base légale d'une ligne à 0 % (contrat AGR200) ────────────────
const CORPS_AGRICOLE = documentContrat('ventes', 'devis_replace_lines_entete').corps_agricole

test('AGR218 — tva_base_legale fait l’aller-retour serveur → écran → payload', () => {
  const ecran = lignesServeurVersEcran(
    CORPS_AGRICOLE.lignes.map((l, i) => ({ id: i + 1, ...l })), '20.00')
  assert.equal(ecran[0].tvaBaseLegale, CORPS_AGRICOLE.lignes[0].tva_base_legale)
  const payload = lignesEcranVersPayload(ecran)
  assert.deepEqual(payload.map(p => p.tva_base_legale),
    CORPS_AGRICOLE.lignes.map(l => l.tva_base_legale))
  assert.deepEqual(payload.map(p => parseFloat(p.taux_tva)),
    CORPS_AGRICOLE.lignes.map(l => parseFloat(l.taux_tva)))
})

test('AGR218 — aucune ligne n’est mise à 0 % automatiquement', () => {
  const lignes = documentContrat('ventes', 'devis_replace_lines_entete').corps.lignes
  const payload = lignesEcranVersPayload(lignesServeurVersEcran(lignes, '20.00'))
  assert.ok(payload.every(p => parseFloat(p.taux_tva) > 0))
  assert.ok(payload.every(p => p.tva_base_legale === ''))
})

test('AGR218 — ligne à 0 % sans base ⇒ manquante ; avec base ou taux > 0 ⇒ non', () => {
  const [pompe, variateur] = lignesServeurVersEcran(CORPS_AGRICOLE.lignes, '20.00')
  assert.equal(baseLegaleManquante(pompe), false)
  assert.equal(baseLegaleManquante({ ...pompe, tvaBaseLegale: '  ' }), true)
  assert.equal(baseLegaleManquante(variateur), false)
  assert.equal(baseLegaleManquante({ typeLigne: 'note', taux_tva: '0' }), false)
})

test('AGR218 — le 400 serveur (champ lignes[i].tva_base_legale) revient sur SA ligne', () => {
  const refus = exempleContrat('ventes', 'devis_replace_lines_entete', 'exemple_400_tva_base_legale')
  const ecran = [
    { _key: 'vide', produit: '', quantite: '1', typeLigne: 'produit' },  // non envoyée
    ...lignesServeurVersEcran(CORPS_AGRICOLE.lignes, '20.00')
      .map((l, i) => ({ ...l, _key: `k${i}` })),
  ]
  assert.deepEqual(erreursBaseLegaleServeur(refus, ecran), { k0: refus.detail })
  assert.deepEqual(erreursBaseLegaleServeur({ detail: 'autre' }, ecran), {})
  assert.deepEqual(erreursBaseLegaleServeur(null, ecran), {})
})
