// VX249(b) — le taux de TVA pré-rempli sur une ligne AJOUTÉE À LA MAIN est une
// SUPPOSITION, et l'écran doit le DIRE. Le drapeau `_tvaSuggested` marque la
// ligne « taux suggéré, modifiable » ; il tombe dès que le vendeur touche
// lui-même le taux — sur CETTE ligne seulement.
//
// QJR109 — CE FICHIER A CESSÉ DE LIRE LE SOURCE. Il épinglait par expression
// régulière deux fichiers (`DevisGenerator.jsx`, `DevisLineRow.jsx`) : la
// présence du texte `_tvaSuggested: true` dans une fenêtre de 800 caractères
// après `const emptyLine = () => ({`. Une épingle qui rougit au premier
// reformatage et reste verte si le drapeau n'est plus jamais LU.
//
// La règle vit désormais dans le module PUR
// `features/ventes/quote/hooks/useDevisLignesPur.js` (QJR90) : elle est ici
// EXÉCUTÉE — on écrit un champ, on change un produit, on demande une
// suggestion, et on regarde ce que les lignes deviennent.
//
// CE QUI RESTE HORS DE PORTÉE D'UN TEST PUR (pas revendiqué ici) : la classe
// CSS `vx-suggested-field` et l'attribut `title` posés par `DevisLineRow` —
// c'est un rendu React, donc une spec RTL.
//
// Run : node --test src/pages/ventes/DevisGeneratorVX249Suggested.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  ecrireChamp, changerProduit, appliquerTarif, suggestionTva, lignesUtilisables,
} from '../../features/ventes/quote/hooks/useDevisLignesPur.js'

const PANNEAU = {
  _key: 1, produit: '10', designation: 'Panneau JA Solar 710W',
  quantite: '12', prix_unit_ttc: '1000', taux_tva: '20', _tvaSuggested: true,
}
const ONDULEUR = {
  _key: 2, produit: '20', designation: 'Onduleur hybride Deye 5 kW',
  quantite: '1', prix_unit_ttc: '15000', taux_tva: '20', _tvaSuggested: true,
}
const LIGNES = [PANNEAU, ONDULEUR]

// ── LA SUGGESTION SIGNALE, ELLE NE RECALE JAMAIS ───────────────────────────

test('un panneau à 20 % est signalé INCOHÉRENT — sans que le taux tapé bouge', () => {
  const s = suggestionTva(PANNEAU)
  assert.equal(s.attendu, 10, 'les panneaux relèvent du taux réduit')
  assert.equal(s.coherent, false)
  assert.equal(PANNEAU.taux_tva, '20', 'la ligne n’est PAS recalée : l’écran signale')
})

test('un panneau au taux attendu est cohérent — aucun signalement à afficher', () => {
  const s = suggestionTva({ ...PANNEAU, taux_tva: '10' })
  assert.equal(s.attendu, 10)
  assert.equal(s.coherent, true)
})

test('une ligne NON panneau attend le taux standard', () => {
  const s = suggestionTva(ONDULEUR)
  assert.equal(s.attendu, 20)
  assert.equal(s.coherent, true)
})

test('un taux ILLISIBLE n’est jamais déclaré cohérent (ni corrigé en douce)', () => {
  for (const taux of ['', 'abc', null, undefined]) {
    const s = suggestionTva({ ...ONDULEUR, taux_tva: taux })
    assert.equal(s.coherent, false, `taux ${JSON.stringify(taux)}`)
    assert.equal(typeof s.attendu, 'number')
  }
})

test('une ligne sans désignation ne casse rien et reçoit le taux standard', () => {
  const s = suggestionTva({})
  assert.equal(s.attendu, 20)
  assert.equal(s.coherent, false)
  assert.equal(suggestionTva(null).coherent, false)
})

test('les repères TVA de la société surchargent la suggestion (jamais un taux codé en dur)', () => {
  assert.equal(suggestionTva(PANNEAU, { tvaPanneaux: 7 }).attendu, 7,
    'la configuration société décide, pas le module')
  assert.equal(suggestionTva(ONDULEUR, { tvaStandard: 14 }).attendu, 14)
  assert.equal(suggestionTva(PANNEAU, { tvaPanneaux: 0 }).attendu, 10,
    'un repère à zéro n’est pas un repère : on retombe sur le défaut')
})

// ── LE DRAPEAU « SUGGÉRÉ » TOMBE QUAND LE VENDEUR TRANCHE ──────────────────

test('modifier le TAUX retire le drapeau « suggéré » — c’est le vendeur qui a tranché', () => {
  const [panneau, onduleur] = ecrireChamp(LIGNES, 1, 'taux_tva', '10')
  assert.equal(panneau.taux_tva, '10')
  assert.equal(panneau._tvaSuggested, false)
  assert.equal(onduleur._tvaSuggested, true, 'sur CETTE ligne seulement')
})

test('modifier un AUTRE champ ne retire pas le drapeau (le taux reste une supposition)', () => {
  for (const champ of ['quantite', 'designation', 'prix_unit_ttc']) {
    const [panneau] = ecrireChamp(LIGNES, 1, champ, '99')
    assert.equal(panneau._tvaSuggested, true, `champ ${champ}`)
  }
})

test('une clé de ligne inconnue ne modifie AUCUNE ligne', () => {
  const apres = ecrireChamp(LIGNES, 999, 'taux_tva', '10')
  assert.deepEqual(apres, LIGNES)
})

test('l’écriture ne mute jamais les lignes d’origine (l’état précédent reste lisible)', () => {
  const apres = ecrireChamp(LIGNES, 1, 'taux_tva', '10')
  assert.notEqual(apres[0], LIGNES[0])
  assert.equal(LIGNES[0]._tvaSuggested, true)
  assert.equal(LIGNES[0].taux_tva, '20')
})

// ── N2 — LE PRIX TAPÉ À LA MAIN, MÊME PATRON ───────────────────────────────

test('N2 — taper un PRIX pose le verrou `prixManuel` sur cette ligne', () => {
  const [panneau, onduleur] = ecrireChamp(LIGNES, 1, 'prix_unit_ttc', '1234')
  assert.equal(panneau.prix_unit_ttc, '1234')
  assert.equal(panneau.prixManuel, true)
  assert.notEqual(onduleur.prixManuel, true)
})

test('N2 — une liste de prix client ne réécrit JAMAIS un prix verrouillé', () => {
  const verrouillees = ecrireChamp(LIGNES, 1, 'prix_unit_ttc', '1234')
  const { lignes, badge } = appliquerTarif(verrouillees, 1,
    { prix: 800, source: 'liste', liste_nom: 'Grands comptes' })
  assert.equal(lignes[0].prix_unit_ttc, '1234', 'le prix négocié survit au tarif')
  assert.equal(badge, 'Grands comptes')
})

test('N2 — un prix NON verrouillé accepte bien le tarif de la liste', () => {
  const { lignes, badge } = appliquerTarif(LIGNES, 1,
    { prix: 800, source: 'liste', liste_nom: 'Grands comptes' })
  assert.equal(lignes[0].prix_unit_ttc, '800')
  assert.equal(lignes[1].prix_unit_ttc, '15000', 'les autres lignes ne bougent pas')
  assert.equal(badge, 'Grands comptes')
})

test('N2 — un tarif STANDARD ne pose aucun badge et ne touche à rien', () => {
  const { lignes, badge } = appliquerTarif(LIGNES, 1, { prix: 800, source: 'standard' })
  assert.equal(badge, null, 'le badge doit être RETIRÉ hors liste dédiée')
  assert.deepEqual(lignes, LIGNES)
  assert.deepEqual(appliquerTarif(LIGNES, 1, null), { lignes: LIGNES, badge: null })
})

test('N2 — resélectionner un PRODUIT lève le verrou : le catalogue reprend la main', () => {
  const verrouillees = ecrireChamp(LIGNES, 1, 'prix_unit_ttc', '1234')
  const [panneau] = changerProduit(verrouillees, 1, { id: 77, nom: 'Panneau Longi 620W' })
  assert.equal(panneau.produit, '77')
  assert.equal(panneau.designation, 'Panneau Longi 620W')
  assert.equal(panneau.prixManuel, false)
})

test('changer de produit sans produit fourni vide la référence sans perdre la désignation', () => {
  const [panneau] = changerProduit(LIGNES, 1, null)
  assert.equal(panneau.produit, '')
  assert.equal(panneau.designation, 'Panneau JA Solar 710W')
})

// ── CE QUI PART RÉELLEMENT AU SERVEUR ──────────────────────────────────────

test('seules les lignes avec un produit ET une quantité > 0 sont enregistrables', () => {
  const utilisables = lignesUtilisables([
    PANNEAU,
    { ...ONDULEUR, quantite: '0' },
    { ...ONDULEUR, _key: 3, produit: '' },
    { ...ONDULEUR, _key: 4, quantite: 'abc' },
  ])
  assert.equal(utilisables.length, 1)
  assert.equal(utilisables[0]._key, 1)
  assert.deepEqual(lignesUtilisables(null), [])
})
