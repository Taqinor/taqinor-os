// EZ12 — L'encaissement offre sa suite (la BONNE : les Encaissements, pas le
// rapprochement bancaire).
// PRÉMISSE CORRIGÉE : `/comptabilite/rapprochements` est le rapprochement
// relevé ↔ grand-livre, « STRICTEMENT DISTINCT de l'import de paiements
// clients » (compta/models.py) — un paiement fraîchement encaissé n'y apparaît
// PAS tant que le relevé n'est pas importé. La suite honnête est donc la page
// des Encaissements, filtrée sur le client.
// Et : « Suggestions » + « Accepter les non-ambiguës » — le chemin 3 clics —
// étaient ENFERMÉS dans la modale de détail.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.join(__dirname, '..', '..')
const read = (rel) => readFileSync(path.join(SRC, rel), 'utf8')
const factures = read('pages/ventes/FactureList.jsx')
const rappro = read('features/compta/pages/RapprochementsPage.jsx')
const paiements = read('pages/ventes/PaiementsPage.jsx')

test('après l’encaissement, la suite est OFFERTE', () => {
  assert.match(factures, /data-testid="encaissement-suite"/)
  assert.match(factures, /data-testid="voir-encaissement"/)
  assert.match(factures, /setDernierEncaissement\(payTarget\)/)
})

test('la suite pointe les ENCAISSEMENTS, filtrés sur le client', () => {
  assert.match(factures, /\/ventes\/paiements\?client=\$\{dernierEncaissement\.client\}/)
  // …et la page cible lit bien ce paramètre (rien d'invente).
  assert.match(paiements, /searchParams\.get\('client'\)/)
  // Surtout PAS le rapprochement bancaire : un paiement encaissé n'y est pas.
  const code = factures.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
  assert.doesNotMatch(code, /comptabilite\/rapprochements/)
})

test('un client absent ne fabrique pas un lien cassé', () => {
  assert.match(factures, /: '\/ventes\/paiements'/)
})

test('le chemin 3-clics sort de la modale : action de PREMIER NIVEAU', () => {
  assert.match(rappro, /id: 'suggestions', label: 'Suggestions d’appariement'/)
  assert.match(rappro, /onClick: \(\) => setSuggestionsFor\(row\)/)
  assert.match(rappro, /const \[suggestionsFor, setSuggestionsFor\] = useState\(null\)/)
})

test('c’est le MÊME dialogue de suggestions, jamais un second', () => {
  // Une seule définition du composant, deux points de montage.
  assert.equal((rappro.match(/function SuggestionsDialog\(/g) || []).length, 1)
  assert.equal((rappro.match(/<SuggestionsDialog/g) || []).length, 2)
  // « Accepter les non-ambiguës » reste l'action de ce dialogue unique.
  assert.match(rappro, /Accepter les non-ambiguës/)
})
