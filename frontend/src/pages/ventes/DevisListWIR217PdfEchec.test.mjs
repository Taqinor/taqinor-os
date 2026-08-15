// WIR217 — sondage PDF : plus de boucle sans fin, plus de toast répété, et un
// ÉCHEC TERMINAL visible et actionnable.
//
// Le payload n'est PAS écrit à la main ici : il est IMPORTÉ du contrat committé
// `apps/ventes/contract_samples/devis_pdf_statut.json` — le même fichier que le
// test backend affirme (PACT10 : une seule source de vérité pour les deux
// moitiés). Assertions au niveau SOURCE (pas de node_modules dans ce worktree).
//   node --test src/pages/ventes/DevisListWIR217PdfEchec.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')
const API = readFileSync(join(HERE, '../../api/ventesApi.js'), 'utf8')
const CONTRAT = JSON.parse(readFileSync(join(
  HERE, '../../../../backend/django_core/apps/ventes/contract_samples/devis_pdf_statut.json',
), 'utf8'))

const genererUnPdfBody = SRC.slice(
  SRC.indexOf('const genererUnPdf = async'),
  SRC.indexOf('const handleGenererPdf = async'))

test('WIR217 : le contrat committé porte bien les trois états du serveur', () => {
  assert.equal(CONTRAT.endpoint, 'GET /api/django/ventes/devis/<int:pk>/pdf-statut/')
  assert.equal(CONTRAT.exemple.statut, 'echec')
  assert.equal(CONTRAT.exemple_pret.statut, 'pret')
  assert.equal(CONTRAT.exemple_en_cours.statut, 'en_cours')
  assert.deepEqual(
    Object.keys(CONTRAT.exemple).sort(),
    ['devis_id', 'erreur', 'fichier_pdf', 'statut'])
})

test('WIR217 : ventesApi expose getDevisPdfStatut sur le chemin du contrat', () => {
  assert.match(
    API,
    /getDevisPdfStatut: \(id\) => api\.get\(`\/ventes\/devis\/\$\{id\}\/pdf-statut\/`\)/)
})

test("WIR217(c) : le sondage LIT le statut et S'ARRÊTE sur l'échec terminal", () => {
  assert.match(genererUnPdfBody, /ventesApi\.getDevisPdfStatut\(d\.id\)/)
  // La valeur testée est celle du CONTRAT, pas une chaîne inventée ici.
  assert.ok(genererUnPdfBody.includes(`st?.statut === '${CONTRAT.exemple.statut}'`))
  const idx = genererUnPdfBody.indexOf(`st?.statut === '${CONTRAT.exemple.statut}'`)
  const bloc = genererUnPdfBody.slice(idx, idx + 600)
  // Arrêt franc : un `return` AVANT toute replanification.
  assert.match(bloc, /return\s*\/\/ on ARRÊTE le sondage/)
  // Et une sortie actionnable, pas un cul-de-sac.
  assert.match(bloc, /label: 'Réessayer'/)
  assert.match(bloc, /onClick: \(\) => genererUnPdf\(d, \{ autoOpen \}\)/)
})

test('WIR217(a) : le toast « toujours en cours » ne part QU\'UNE fois', () => {
  // La clôture périmée `!pdfSlowPoll[d.id]` (toujours false → toast toutes les
  // 10 s) est remplacée par un drapeau LOCAL au job.
  assert.match(genererUnPdfBody, /let lentAnnonce = false/)
  assert.match(genererUnPdfBody, /if \(slow && !lentAnnonce\)/)
  assert.doesNotMatch(genererUnPdfBody, /if \(slow && !pdfSlowPoll\[d\.id\]\)/)
})

test('WIR217(b) : les minuteries sont retenues et annulées au démontage', () => {
  assert.match(SRC, /const pdfPollTimers = useRef\(new Set\(\)\)/)
  assert.match(SRC, /const pdfPollMonte = useRef\(true\)/)
  assert.match(SRC, /timers\.forEach\(\(t\) => clearTimeout\(t\)\)/)
  // Chaque replanification est retenue…
  assert.match(genererUnPdfBody, /retenirTimerPdf\(setTimeout\(poll, slow \? 10000 : 2000\)\)/)
  assert.match(genererUnPdfBody, /retenirTimerPdf\(setTimeout\(poll, 2000\)\)/)
  // …et un tour qui démarrerait quand même après démontage sort tout de suite.
  assert.match(genererUnPdfBody, /if \(!pdfPollMonte\.current\) return/)
})

test('WIR217 : le contrat QX21 reste littéralement satisfait (aucune assertion touchée)', () => {
  // Les trois affirmations de DevisListPdfPolling.test.mjs, rejouées ici pour
  // que toute future réécriture du sondage voie tout de suite ce qu'elle casse.
  assert.equal((genererUnPdfBody.match(/dispatch\(genererPdfDevis\(/g) ?? []).length, 1)
  assert.match(genererUnPdfBody, /FAST_ATTEMPTS = 15/)
  assert.match(genererUnPdfBody, /const slow = attempts >= FAST_ATTEMPTS/)
  assert.doesNotMatch(genererUnPdfBody, /attempts\+\+ > 15/)
  assert.match(genererUnPdfBody, /setTimeout\(poll, slow \? 10000 : 2000\)/)
  assert.match(SRC, /const isSlowPolling = !!pdfSlowPoll\[d\.id\]/)
  assert.match(SRC, /PDF toujours en cours/)
})
