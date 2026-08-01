// APX13 — la chaîne documentaire est visible PARTOUT, pas seulement sur la
// liste des devis. Ce test verrouille (a) la dérivation de la piste vue d'une
// facture et d'un bon de commande, (b) le fait qu'aucune clé du funnel
// STAGES.py (règle #2) n'entre dans la couche STATUTS DOCUMENT (règle #4),
// (c) le câblage réel des deux nouveaux écrans.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { DOC_STATUT_TRACK, factureTrack, bonCommandeTrack } from './documentChain.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const page = (f) => readFileSync(path.join(__dirname, '..', '..', 'pages', 'ventes', f), 'utf8')

test('la piste est la chaîne DOCUMENT, jamais le funnel STAGES.py (règles #2/#4)', () => {
  assert.deepEqual(
    DOC_STATUT_TRACK.map(s => s.key),
    ['brouillon', 'envoye', 'accepte', 'bc', 'facture', 'chantier'],
  )
  // Les 6 clés canoniques du funnel CRM n'ont RIEN à faire ici.
  const src = readFileSync(path.join(__dirname, 'documentChain.js'), 'utf8')
  for (const stage of ['NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP', 'SIGNED', 'COLD']) {
    assert.doesNotMatch(src, new RegExp(`['"\`]${stage}['"\`]`), `clé de funnel ${stage} interdite`)
  }
})

test('une facture pose la piste sur « Facturé »', () => {
  assert.deepEqual(factureTrack({ statut: 'emise' }), { current: 'facture', blocked: [] })
  assert.deepEqual(factureTrack({ statut: 'payee' }), { current: 'facture', blocked: [] })
})

test('une facture ANNULÉE marque l’anomalie sans faire reculer la piste', () => {
  assert.deepEqual(factureTrack({ statut: 'annulee' }), { current: 'facture', blocked: ['facture'] })
})

test('un bon de commande avance d’un cran une fois facturé', () => {
  assert.deepEqual(bonCommandeTrack({ statut: 'confirme' }), { current: 'bc', blocked: [] })
  assert.deepEqual(
    bonCommandeTrack({ statut: 'livre', has_facture: true }),
    { current: 'facture', blocked: [] },
  )
})

test('un bon de commande annulé marque la puce BC en anomalie', () => {
  assert.deepEqual(bonCommandeTrack({ statut: 'annule' }), { current: 'bc', blocked: ['bc'] })
})

test('la piste est réellement rendue sur les factures ET les bons de commande', () => {
  for (const [file, helper] of [['FactureList.jsx', 'factureTrack'], ['BonCommandeList.jsx', 'bonCommandeTrack']]) {
    const src = page(file)
    assert.match(src, /import DocumentStageTrack from '\.\.\/\.\.\/ui\/DocumentStageTrack'/, `${file}`)
    assert.match(src, new RegExp(`\\{\\.\\.\\.${helper}\\(`), `${file} : piste non dérivée`)
  }
})

test('l’amont est cliquable et pointe sur le paramètre que DevisList lit vraiment', () => {
  // `?ref=` n'est lu nulle part (vérifié) : le lien atterrissait sur la liste
  // nue. `?devis=<id>` est le deep-link QX12 qui surligne et scrolle.
  for (const file of ['FactureList.jsx', 'BonCommandeList.jsx']) {
    const src = page(file)
    assert.match(src, /\/ventes\/devis\?devis=\$\{encodeURIComponent\(/, `${file} : lien amont absent`)
    assert.doesNotMatch(src, /\/ventes\/devis\?ref=/, `${file} : lien mort ?ref= encore présent`)
  }
  // DevisList lit bien ce paramètre.
  assert.match(page('DevisList.jsx'), /searchParams\.get\('devis'\)/)
})

test('la définition de la chaîne n’existe qu’UNE fois', () => {
  // DevisList consommait sa propre copie du tableau : il importe désormais
  // la source partagée.
  const src = page('DevisList.jsx')
  assert.match(src, /import \{ DOC_STATUT_TRACK \} from '\.\.\/\.\.\/features\/ventes\/documentChain'/)
  assert.doesNotMatch(src, /const DOC_STATUT_TRACK = \[/)
})
