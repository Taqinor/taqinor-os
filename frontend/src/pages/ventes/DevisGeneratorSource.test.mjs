// SPL42 — GARDES SUR LE SOURCE CONCATÉNÉ DU GÉNÉRATEUR (`lireSourceGenerateur`).
//
// Les déplacements SPL43-SPL55 répartissent DevisGenerator.jsx en plusieurs
// fichiers : les gardes NÉGATIVES ci-dessous portent sur TOUTE la
// concaténation (jamais sur la seule coquille, sinon elles deviendraient
// vacueuses), et la liste FILES ne rétrécit jamais en silence.
//
// Écrite sans le patron « lecture de source + assertion regex » (garde
// QJR239) : `includes` et `RegExp.test` seulement.
//
// Run : node --test src/pages/ventes/DevisGeneratorSource.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { join, relative } from 'node:path'

import {
  FILES, SRC, lireSourceGenerateur, lireSourceCoquille, fichiersManquants,
} from './DevisGeneratorSource.js'

//: Les régressions déjà corrigées qui ne doivent JAMAIS revenir, où qu'elles soient.
const INTERDITS = [
  'ttcFromHt(l.prix_unitaire',
  'ttcExactFromHt(l.prix_unitaire',
  'prix_unitaire: htFromTtc(',
  'avgBill / quoteLogic.kwhPrice',
]

const premierInterdit = (source) => INTERDITS.find((motif) => source.includes(motif)) ?? null

test('(i) aucune régression interdite dans TOUT le générateur (concaténation)', () => {
  assert.equal(premierInterdit(lireSourceGenerateur()), null)
})

test('(i) la garde voit un fichier ajouté à la liste (golden rouge)', () => {
  const dossier = mkdtempSync(join(SRC, 'pages', 'ventes', '.spl42-'))
  try {
    const fichier = join(dossier, 'faux.js')
    writeFileSync(fichier, 'const x = avgBill / quoteLogic.kwhPrice\n')
    const rel = relative(SRC, fichier).split('\\').join('/')
    assert.equal(premierInterdit(lireSourceGenerateur([...FILES, rel])), 'avgBill / quoteLogic.kwhPrice')
  } finally {
    rmSync(dossier, { recursive: true, force: true })
  }
})

test('(ii) aucun hook appelé après `if (succes && !embedded)` (nombre de hooks stable)', () => {
  const coquille = lireSourceCoquille()
  const idx = coquille.indexOf('if (succes && !embedded)')
  assert.ok(idx > -1, 'retour anticipé « succès » introuvable')
  const apres = coquille.slice(idx)
  const hook = /\buse[A-Z][A-Za-z0-9]*\(/.exec(apres)
  assert.equal(hook, null, `hook appelé après le retour anticipé : ${hook?.[0]}`)
})

test('(iii) chaque entrée de FILES existe ; la coquille est la première', () => {
  assert.deepEqual(fichiersManquants(), [])
  assert.equal(FILES[0], 'pages/ventes/DevisGenerator.jsx')
  assert.ok(lireSourceGenerateur().includes(lireSourceCoquille()))
})
