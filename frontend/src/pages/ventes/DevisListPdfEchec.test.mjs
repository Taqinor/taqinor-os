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
import { lireSourcesDevisList } from './devisList/lireSources.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
// SPL204 — le flux PDF vit dans devisList/useDevisPdf.js : DevisList.jsx +
// devisList/*.{js,jsx} (le code suit son déplacement, assertions intactes).
const SRC = lireSourcesDevisList()
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
    /etatPdfDevis:[\s\S]*?api\.get\(`\/ventes\/devis\/\$\{id\}\/etat-pdf\/`[,)]/)
})

// R1-02/R1-03 — le dialogue suit SA demande : ni « prêt » ni fichier d'un autre
// format demandé avant ou après (clé `demande` de generer-pdf, additive).
test('le sondage et l’ouverture suivent la demande rendue par generer-pdf', () => {
  assert.match(genererUnPdfBody, /const lance = await dispatch\(genererPdfDevis\(/)
  assert.match(genererUnPdfBody, /lance\?\.demande/)
  assert.match(genererUnPdfBody, /ventesApi\.etatPdfDevis\(d\.id, \.\.\.suivi\)/)
  const ouvertures = genererUnPdfBody.match(/ventesApi\.telechargerPdfDevis\([^)]*\)/g) ?? []
  assert.ok(ouvertures.length >= 2)
  for (const appel of ouvertures) assert.equal(appel, 'ventesApi.telechargerPdfDevis(d.id, ...suivi)')
  assert.match(API, /etatPdfDevis: \(id, demande\) =>[^\n]*params: demande \? \{ demande \} : \{\}/)
})

// ── Le sondage lit l'ÉTAT, plus seulement `fichier_pdf` ─────────────────────

test('le sondage interroge etat-pdf (et non plus le devis entier)', () => {
  assert.match(genererUnPdfBody, /ventesApi\.etatPdfDevis\(d\.id[,)]/)
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

// ACAL1236 — un sondage manqué replanifie, mais après 5 manqués DE SUITE le
// sondage le dit (« la vérification du PDF a échoué — Réessayer ») et s'arrête ;
// un sondage réussi remet le compte à zéro.
test('ACAL1236 — 5 sondages manqués de suite : message + Réessayer, arrêt ; un succès remet à zéro', () => {
  const catchBloc = genererUnPdfBody.slice(genererUnPdfBody.indexOf('sondage manqué'))
  assert.match(genererUnPdfBody, /let manquesDeSuite = 0/)
  assert.match(genererUnPdfBody, /manquesDeSuite = 0\r?\n/)
  assert.match(catchBloc, /manquesDeSuite \+= 1/)
  assert.match(catchBloc, /manquesDeSuite >= 5/)
  assert.match(catchBloc, /la vérification du PDF a échoué/)
  assert.match(catchBloc, /label: 'Réessayer'/)
  // La replanification au même pas reste là pour les manqués isolés.
  assert.match(catchBloc, /setTimeout\(poll, slow \? 10000 : 2000\)/)
})
