// WIR217 — La génération d'un PDF de devis pouvait échouer DÉFINITIVEMENT
// (retries Celery épuisés) sans que rien ne l'apprenne à l'utilisateur : le
// sondage ne lisait que `fichier_pdf`, tournait sans fin, répétait son toast
// « toujours en cours » toutes les 10 s, et survivait au démontage de l'écran.
//
// Vérifié contre la SOURCE (ce worktree n'a pas de node_modules, comme
// DevisListPdfPolling.test.mjs — QX21 — dont les assertions restent INTACTES) :
//   node --test src/pages/ventes/DevisListPdfEchec.test.mjs
//
// La charge utile n'est PAS écrite à la main : elle vient de l'exemple COMMITTÉ
// `apps/ventes/contract_samples/devis_etat_pdf.json` (PACT10), le même que le
// test backend affirme et que `scripts/check_api_shapes.py` compare au
// dictionnaire réellement renvoyé par la vue.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { documentContrat, exempleContrat } from '../../test/fixtures/contractSamples.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')
const API = readFileSync(join(HERE, '..', '..', 'api', 'ventesApi.js'), 'utf8')

const genererUnPdfBody = SRC.slice(
  SRC.indexOf('const genererUnPdf = async'),
  SRC.indexOf('const handleGenererPdf = async'))

// ── Le contrat partagé ──────────────────────────────────────────────────────

test('le contrat devis_etat_pdf est committé et décrit l’endpoint etat-pdf', () => {
  const doc = documentContrat('ventes', 'devis_etat_pdf')
  assert.equal(doc.endpoint, 'GET /api/django/ventes/devis/{id}/etat-pdf/')
  const exemple = exempleContrat('ventes', 'devis_etat_pdf')
  assert.deepEqual(
    Object.keys(exemple).sort(),
    ['date', 'devis', 'erreur', 'fichier_pdf', 'statut'])
  // Les trois états du serveur, jamais trois FORMES différentes.
  for (const variante of ['exemple', 'exemple_pret', 'exemple_en_cours']) {
    assert.deepEqual(
      Object.keys(exempleContrat('ventes', 'devis_etat_pdf', variante)).sort(),
      Object.keys(exemple).sort(), variante)
  }
  assert.equal(exempleContrat('ventes', 'devis_etat_pdf').statut, 'echec')
  assert.equal(exempleContrat('ventes', 'devis_etat_pdf', 'exemple_pret').statut, 'pret')
  assert.equal(
    exempleContrat('ventes', 'devis_etat_pdf', 'exemple_en_cours').statut, 'en_cours')
})

test('le wrapper etatPdfDevis vise l’URL RÉELLE du contrat', () => {
  assert.match(
    API,
    /etatPdfDevis:[\s\S]*?api\.get\(`\/ventes\/devis\/\$\{id\}\/etat-pdf\/`\)/)
})

// ── Le sondage lit l'ÉTAT, plus seulement `fichier_pdf` ─────────────────────

test('le sondage interroge etat-pdf (et non plus le devis entier)', () => {
  assert.match(genererUnPdfBody, /ventesApi\.etatPdfDevis\(d\.id\)/)
  assert.doesNotMatch(genererUnPdfBody, /ventesApi\.getDevisById\(d\.id\)/)
})

test('un statut « echec » ARRÊTE le sondage et propose « Réessayer »', () => {
  const exemple = exempleContrat('ventes', 'devis_etat_pdf')
  // La clé lue par l'écran est bien celle du contrat.
  assert.ok(Object.prototype.hasOwnProperty.call(exemple, 'statut'))
  assert.ok(Object.prototype.hasOwnProperty.call(exemple, 'erreur'))
  assert.match(genererUnPdfBody, /res\.data\.statut === 'echec'/)
  assert.match(genererUnPdfBody, /res\.data\.erreur/)
  assert.match(genererUnPdfBody, /label: 'Réessayer'/)
  // La branche d'échec SORT de la boucle : pas de `setTimeout` derrière elle.
  const branche = genererUnPdfBody.slice(
    genererUnPdfBody.indexOf("res.data.statut === 'echec'"),
    genererUnPdfBody.indexOf('if (res.data.fichier_pdf)'))
  assert.doesNotMatch(branche, /setTimeout/)
  assert.match(branche, /return\s*$/m)
})

// ── Le drapeau « lent » ne parle plus qu'UNE fois ───────────────────────────

test('le toast « toujours en cours » n’est plus lu dans une clôture périmée', () => {
  // `pdfSlowPoll[d.id]` était figé à `false` dans la clôture : la condition
  // restait vraie et le toast repartait à chaque tour lent.
  assert.doesNotMatch(genererUnPdfBody, /slow && !pdfSlowPoll\[d\.id\]/)
  assert.match(genererUnPdfBody, /let slowAnnonce = false/)
  assert.match(genererUnPdfBody, /slow && !slowAnnonce/)
  assert.match(genererUnPdfBody, /slowAnnonce = true/)
})

// ── Plus aucun sondage après démontage ─────────────────────────────────────

test('les minuteries sont mémorisées puis nettoyées au démontage', () => {
  assert.match(SRC, /const pollTimers = useRef\(\{\}\)/)
  assert.match(SRC, /const pollAnnule = useRef\(false\)/)
  // Chaque replanification passe par le registre de minuteries.
  assert.doesNotMatch(genererUnPdfBody, /^\s*setTimeout\(poll,/m)
  assert.match(genererUnPdfBody, /pollTimers\.current\[d\.id\] = setTimeout\(poll, 2000\)/)
  assert.match(
    genererUnPdfBody,
    /pollTimers\.current\[d\.id\] = setTimeout\(poll, slow \? 10000 : 2000\)/)
  // Le nettoyage de démontage existe et vide le registre.
  assert.match(SRC, /Object\.values\(timers\)\.forEach\(clearTimeout\)/)
  assert.match(SRC, /pollAnnule\.current = true/)
})

test('la boucle se tait immédiatement si l’écran est démonté', () => {
  assert.match(genererUnPdfBody, /if \(pollAnnule\.current\) return/)
})
