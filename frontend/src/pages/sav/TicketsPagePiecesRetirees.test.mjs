// WIR232/ZMFG8/XMFG10 — vue unifiée Ajout/Retrait/Recyclage des pièces d'un
// ticket (`getTicketPiecesUnifiees`, jamais consommée jusqu'ici) + formulaire
// « Retirer une pièce » (destination/opération/n° série) TRACÉ, contrairement
// au bouton « Retirer » historique qui SUPPRIME la ligne de consommation sans
// aucune trace. Vérification de SOURCE (JSX, pas de node_modules installés
// dans ce lane — cf. SigneDialog.test.mjs).
//   node --test src/pages/sav/TicketsPagePiecesRetirees.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'TicketsPage.jsx'), 'utf8')
const API_SRC = readFileSync(join(HERE, '..', '..', 'api', 'savApi.js'), 'utf8')

test('savApi expose getTicketPiecesRetirees et retirerTicketPiece (WIR232)', () => {
  assert.match(API_SRC, /getTicketPiecesRetirees: \(id\) => api\.get\(`\/sav\/tickets\/\$\{id\}\/pieces-retirees\/`\)/)
  assert.match(API_SRC, /retirerTicketPiece: \(id, body\) => api\.post\(`\/sav\/tickets\/\$\{id\}\/pieces-retirees\/`, body\)/)
})

test('la vue unifiée charge getTicketPiecesUnifiees et rend data-testid="pieces-unifiees-liste"', () => {
  assert.match(SRC, /const loadPiecesUnifiees = \(\) => \{/)
  assert.match(SRC, /savApi\.getTicketPiecesUnifiees\(id\)/)
  assert.match(SRC, /data-testid="pieces-unifiees-liste"/)
  // Chargée au montage, comme les autres listes du ticket.
  assert.match(SRC, /loadPieces\(\)\s*\n\s*loadPiecesUnifiees\(\)/)
})

test('retirerPiece envoie exactement {produit, quantite, destination, operation, numero_serie}', () => {
  const body = SRC.slice(SRC.indexOf('const retirerPiece = async'), SRC.indexOf('const annuler = async'))
  assert.match(body, /savApi\.retirerTicketPiece\(id, \{/)
  assert.match(body, /produit: retraitForm\.produit/)
  assert.match(body, /quantite: retraitForm\.quantite \|\| '1'/)
  assert.match(body, /destination: retraitForm\.destination/)
  assert.match(body, /operation: retraitForm\.operation/)
  assert.match(body, /numero_serie: retraitForm\.numero_serie/)
})

test('un échec (400) affiche le message FR SANS vider le formulaire', () => {
  const body = SRC.slice(SRC.indexOf('const retirerPiece = async'), SRC.indexOf('const annuler = async'))
  // Le reset (`setRetraitForm({ produit: ''...`) vit dans le chemin de
  // SUCCÈS, jamais dans le `catch`.
  const tryIdx = body.indexOf('try {')
  const catchIdx = body.indexOf('} catch (err) {')
  const trySection = body.slice(tryIdx, catchIdx)
  const catchSection = body.slice(catchIdx)
  assert.match(trySection, /setRetraitForm\(\{ produit: ''/)
  assert.doesNotMatch(catchSection, /setRetraitForm\(\{ produit: ''/)
  assert.match(catchSection, /setRetraitError\(frError\(err, 'Échec du retrait de la pièce\.'\)\)/)
})

test('la destination/opération proposent les 3+2 valeurs canoniques du serveur', () => {
  const formBlock = SRC.slice(SRC.indexOf('label="Destination"'), SRC.indexOf('label="N° série"'))
  assert.match(formBlock, /value="rebut"/)
  assert.match(formBlock, /value="retour_fournisseur"/)
  assert.match(formBlock, /value="stock_occasion"/)
  assert.match(formBlock, /value="retrait"/)
  assert.match(formBlock, /value="recyclage"/)
})
