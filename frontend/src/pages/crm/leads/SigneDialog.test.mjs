// Régressions du dialogue « Signé » (L420 aperçu PDF inline, L423 détail par
// option). On vérifie les invariants de SOURCE (le fichier est du JSX, donc non
// importable par node:test) plus la logique pure ré-implémentée à l'identique.
// NB : ce fichier n'est PAS encore câblé dans le job CI
// (.github/workflows/ci.yml, hors périmètre de ce lane) ; à exécuter :
//   node --test src/pages/crm/leads/SigneDialog.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'SigneDialog.jsx'), 'utf8')

test('L420 : aperçu PDF inline réutilise PdfCanvas + previewPdf (jamais dupliqué)', () => {
  assert.match(SRC, /from '\.\.\/\.\.\/\.\.\/features\/ventes\/previewPdf'/)
  assert.match(SRC, /import\('\.\.\/\.\.\/\.\.\/features\/ventes\/PdfCanvas'\)/)
  assert.match(SRC, /getProposalPdf\(/)
  assert.match(SRC, /proposalParams\(/)
  assert.match(SRC, /<PdfCanvas/)
})

test('L423 : détail par option (kWc / total TTC) affiché à côté des radios', () => {
  assert.match(SRC, /optionsDetail/)
  assert.match(SRC, /det\.kwc/)
  assert.match(SRC, /fmtMAD\(det\.ttc\)/)
})

// VX40/VX155 — le passage envoyé→accepté est le SEUL moment célébré de
// l'app : la carte de victoire <DealSignedCelebration> (montant + kWc réels)
// remplace le toast plat, câblée juste après le POST accepterDevis ;
// onConfirmed() n'est appelé qu'à la fermeture de la carte (jamais avant que
// le vendeur l'ait vue).
test('VX40/VX155 : acceptation confirmée déclenche la carte de victoire', () => {
  assert.match(SRC, /from '\.\.\/\.\.\/\.\.\/ui\/DealSignedCelebration'/)
  assert.match(SRC, /await ventesApi\.accepterDevis\(selected\.id, \{ nom, date, option \}\)/)
  assert.match(SRC, /setCelebration\(\{/)
  assert.match(SRC, /<DealSignedCelebration/)
  assert.match(SRC, /onClose=\{\(\) => \{ setCelebration\(null\); onConfirmed\?\.\(\) \}\}/)
})

// LW5 — le défaut du champ date (L121) et la comparaison « date future »
// (dans confirm()) doivent tous deux passer par todayLocalStr() (date civile
// LOCALE) ; plus jamais new Date().toISOString().slice(0,10) (date UTC, qui
// décale d'un jour côté fuseau local autour de minuit — recon 05 P2#9).
test('LW5 : date par défaut + comparaison "future" en LOCAL, jamais toISOString() UTC', () => {
  assert.doesNotMatch(SRC, /new Date\(\)\.toISOString\(\)\.slice\(0, ?10\)/)
  assert.match(SRC, /function todayLocalStr\(now = new Date\(\)\)/)
  assert.match(SRC, /toLocaleDateString\('fr-CA'\)/)
  assert.match(SRC, /useState\(\(\) => todayLocalStr\(\)\)/)
  assert.match(SRC, /const today = todayLocalStr\(\)/)
})

// La carte elle-même reste responsable du burst CSS-only VX40 (posé une
// seule fois, jamais dupliqué dans SigneDialog).
test('DealSignedCelebration : réutilise celebrateDealSigned (VX40), montant + kWc réels', () => {
  const CELEB_SRC = readFileSync(
    join(HERE, '..', '..', '..', 'ui', 'DealSignedCelebration.jsx'), 'utf8')
  assert.match(CELEB_SRC, /from '\.\/celebrate'/)
  assert.match(CELEB_SRC, /celebrateDealSigned\(\)/)
  assert.match(CELEB_SRC, /formatMAD\(montantTtc\)/)
  assert.match(CELEB_SRC, /kwc/)
})

// ── Logique pure de optionsDetail, ré-implémentée à l'identique pour la tester
//    sans parseur JSX (le code source ci-dessus en garantit la présence). ──
const isBatteryLine = (d) =>
  (d || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .includes('batterie')
function ligneTtc(l, devisTva) {
  const qte = parseFloat(l.quantite) || 0
  const pu = parseFloat(l.prix_unitaire) || 0
  const rem = parseFloat(l.remise) || 0
  const tva = (l.taux_tva != null && l.taux_tva !== '')
    ? (parseFloat(l.taux_tva) || 0) : (parseFloat(devisTva) || 0)
  return qte * pu * (1 - rem / 100) * (1 + tva / 100)
}
function optionsDetail(devis) {
  const lignes = devis?.lignes ?? []
  if (!lignes.length) return null
  const tva = devis?.taux_tva
  const factor = 1 - (parseFloat(devis?.remise_globale) || 0) / 100
  const ttcAvec = lignes.reduce((s, l) => s + ligneTtc(l, tva), 0) * factor
  const ttcSans = lignes.filter((l) => !isBatteryLine(l.designation))
    .reduce((s, l) => s + ligneTtc(l, tva), 0) * factor
  const nbPanneaux = lignes
    .filter((l) => (l.designation || '').toLowerCase().includes('panneau'))
    .reduce((s, l) => s + (parseFloat(l.quantite) || 0), 0)
  const kwc = nbPanneaux > 0 ? Math.round(nbPanneaux * 0.71 * 100) / 100 : null
  return {
    sans_batterie: { ttc: ttcSans, kwc },
    avec_batterie: { ttc: ttcAvec, kwc },
  }
}

const devis = {
  taux_tva: '20', remise_globale: '0',
  lignes: [
    { designation: 'Panneau 710W', quantite: '10', prix_unitaire: '1000', remise: '0', taux_tva: '10' },
    { designation: 'Onduleur hybride', quantite: '1', prix_unitaire: '5000', remise: '0', taux_tva: '20' },
    { designation: 'Batterie LiFePO4', quantite: '1', prix_unitaire: '8000', remise: '0', taux_tva: '20' },
  ],
}

test('optionsDetail : sans batterie exclut la ligne batterie', () => {
  const d = optionsDetail(devis)
  assert.equal(Math.round(d.avec_batterie.ttc), 26600) // 11000+6000+9600
  assert.equal(Math.round(d.sans_batterie.ttc), 17000) // 11000+6000
})

test('optionsDetail : kWc estimé (≈ 0,71 kWc/panneau)', () => {
  const d = optionsDetail(devis)
  assert.equal(d.avec_batterie.kwc, 7.1)
})

test('optionsDetail : remise globale appliquée aux deux options', () => {
  const d = optionsDetail({ ...devis, remise_globale: '10' })
  assert.equal(Math.round(d.avec_batterie.ttc), Math.round(26600 * 0.9))
})

test('optionsDetail : null sans lignes ; pas de kWc sans panneaux', () => {
  assert.equal(optionsDetail({ lignes: [] }), null)
  const d = optionsDetail({
    taux_tva: '20', remise_globale: '0',
    lignes: [{ designation: 'Pompe', quantite: '1', prix_unitaire: '5000', remise: '0', taux_tva: '20' }],
  })
  assert.equal(d.avec_batterie.kwc, null)
})

// ── LW5 : todayLocalStr, ré-implémentée à l'identique (le code source
//    ci-dessus en garantit la présence exacte, cf. tests de régression). ──
function todayLocalStr(now = new Date()) {
  return now.toLocaleDateString('fr-CA')
}

// Horloge mockée à 23h30 (référentiel UTC) = 00h30 le LENDEMAIN à Casablanca
// (Africa/Casablanca est fixé à UTC+1 depuis 2018, hors Ramadan) : le jour
// civil LOCAL a déjà changé alors que toISOString() reste bloqué sur la
// veille. C'est exactement la fenêtre (minuit local passé, minuit UTC pas
// encore atteint) où l'ancien code L121/L207-211 affichait « hier » comme
// date par défaut et levait une fausse alerte « date future » pour toute
// date d'aujourd'hui tapée par le vendeur.
test('LW5 : todayLocalStr reste sur le jour civil LOCAL quand toISOString() a déjà basculé sur la veille (23h30 UTC / Casablanca)', () => {
  const previousTz = process.env.TZ
  process.env.TZ = 'Africa/Casablanca'
  try {
    const mocked = new Date('2026-07-18T23:30:00.000Z')
    // Le bug historique (toISOString) resterait bloqué sur la veille :
    assert.equal(mocked.toISOString().slice(0, 10), '2026-07-18')
    // Le jour civil LOCAL (Casablanca) est déjà le lendemain :
    assert.equal(todayLocalStr(mocked), '2026-07-19')
    // Défaut du champ = aujourd'hui LOCAL (jamais "hier") :
    assert.notEqual(todayLocalStr(mocked), mocked.toISOString().slice(0, 10))
    // Une date d'acceptation tapée = aujourd'hui LOCAL ne doit plus jamais
    // sembler « future » face à ce today() corrigé :
    const dateChoisieParLeClient = '2026-07-19'
    assert.ok(!(dateChoisieParLeClient > todayLocalStr(mocked)))
  } finally {
    process.env.TZ = previousTz
  }
})
