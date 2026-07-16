// VX159/VX250 — RelationCounters : les 4 fiches (Lead/Client/Fournisseur/
// Produit) + le détail Devis (DevisForm.jsx, couvert par son propre test)
// consomment TOUTES le même composant — jamais un second construit
// ailleurs. Chaque mount point lit des données déjà chargées (ZÉRO appel
// réseau nouveau où c'est possible) et `prix_achat` ne transite jamais par
// ce composant.
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/ui/RelationCountersMountPoints.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const LEAD_SRC = readFileSync(join(HERE, '../pages/crm/LeadForm.jsx'), 'utf8')
const CLIENT_SRC = readFileSync(join(HERE, '../pages/crm/ClientDetailPanel.jsx'), 'utf8')
const FOURNISSEUR_SRC = readFileSync(join(HERE, '../pages/stock/FournisseurFiche360.jsx'), 'utf8')
const PRODUIT_SRC = readFileSync(join(HERE, '../pages/stock/ProduitDetail.jsx'), 'utf8')

for (const [name, src] of [
  ['LeadForm.jsx', LEAD_SRC],
  ['ClientDetailPanel.jsx', CLIENT_SRC],
  ['FournisseurFiche360.jsx', FOURNISSEUR_SRC],
  ['ProduitDetail.jsx', PRODUIT_SRC],
]) {
  test(`${name} : monte RelationCounters (le même composant partagé, jamais un second)`, () => {
    assert.match(src, /RelationCounters/, `${name} doit importer/monter RelationCounters`)
    // `prix_achat` ne doit jamais être LU/PASSÉ comme donnée (un simple mot
    // dans un commentaire expliquant la règle est légitime — on cherche un
    // accès réel : `.prix_achat` ou une clé d'objet `prix_achat:`).
    assert.doesNotMatch(src, /\.prix_achat\b|\bprix_achat:/, `${name} ne doit JAMAIS accéder à prix_achat`)
  })
}

test('LeadForm.jsx : compteur devis dérivé de liveLead.devis déjà chargé — ZÉRO appel réseau', () => {
  assert.match(LEAD_SRC, /count: liveLead\.devis\.length/)
})

test('ClientDetailPanel.jsx : compteurs dérivés de `data` déjà chargé (endpoint /documents/ existant) — ZÉRO appel réseau nouveau', () => {
  assert.match(CLIENT_SRC, /count: data\.devis\?\.length \?\? 0/)
  assert.match(CLIENT_SRC, /count: data\.factures\?\.length \?\? 0/)
  // chantiers reste un compteur STATIQUE (InstallationsPage.jsx hors périmètre) —
  // jamais un `to` qui prétendrait pré-filtrer sans le pouvoir.
  const chantierLine = CLIENT_SRC.split('\n').find((l) => l.includes("label: 'chantiers'"))
  assert.ok(chantierLine)
  assert.doesNotMatch(chantierLine, /to:/)
})

test('FournisseurFiche360.jsx : le fetch vue-360 est REMONTÉ au parent — RelationCounters et ResumePanel partagent le MÊME appel (jamais un doublon)', () => {
  assert.match(FOURNISSEUR_SRC, /const \[resumeData, setResumeData\] = useState\(null\)/)
  assert.match(FOURNISSEUR_SRC, /<ResumePanel data=\{resumeData\} unavailable=\{resumeUnavailable\} loading=\{resumeLoading\} \/>/)
  assert.doesNotMatch(FOURNISSEUR_SRC, /function ResumePanel\(\{ fournisseurId \}\)/)
})

test('ProduitDetail.jsx : compteur dérivé de produit.bcf_sources_en_commande déjà chargé (prop) — ZÉRO appel réseau', () => {
  assert.match(PRODUIT_SRC, /count: produit\.bcf_sources_en_commande\?\.length \?\? 0/)
})
