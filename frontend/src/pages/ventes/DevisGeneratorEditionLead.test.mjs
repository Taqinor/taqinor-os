// ERR-QAH-VENTES-EDITION-PERD-LEAD — « Éditer » un devis créé depuis un lead
// (`/ventes/devis/nouveau?edit=<id>`) repartait d'un sélecteur de lead VIDE
// (le lead n'était pas dans la première page de `leads`), sans client ni
// factures (grille d'exemple 500/450/400…). Test SOURCE (aucun node_modules) :
//   node --test src/pages/ventes/DevisGeneratorEditionLead.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')
const debut = SRC.indexOf("// ── Édition d'un brouillon (?edit=ID) : préremplissage complet ──")
const EDIT = SRC.slice(debut, SRC.indexOf('}, [editId])', debut))

test('le lead du devis est relu par son id et ajouté aux options du sélecteur', () => {
  assert.ok(debut > 0, 'effet ?edit= introuvable')
  assert.match(EDIT, /crmApi\.getLead\(d\.lead\)/)
  assert.match(EDIT, /setLeadDuDevis\(lead\)/)
  assert.match(SRC, /const leadsListe = \(leadDuDevis/)
  assert.match(SRC, /const selectedLead = leadsListe\.find\(/)
  assert.match(SRC, /\{leadsListe\.map\(l => \(/)
})

test('la relecture du lead est isolée : une panne ne casse pas le chargement du devis', () => {
  assert.match(EDIT, /Promise\.resolve\(\)\.then\(\(\) => crmApi\.getLead\(d\.lead\)\)/)
  assert.match(EDIT, /\}\)\.catch\(\(\) => \{\}\)/)
})

test('factures hiver/été du lead reposées sans écraser une saisie, et 12 factures réelles réaffichées', () => {
  assert.match(EDIT, /setFHiver\(prev => prev \|\| String\(lead\.facture_hiver\)\)/)
  assert.match(EDIT, /setFEte\(prev => prev \|\|/)
  assert.match(EDIT, /if \(factures\) setMonthly\(factures\.map\(v => Number\(v\) \|\| 0\)\)/)
  // Setters BRUTS : rouvrir ne redimensionne jamais (aucun syncBillEstimator).
  assert.doesNotMatch(EDIT, /syncBillEstimator\(/)
})
