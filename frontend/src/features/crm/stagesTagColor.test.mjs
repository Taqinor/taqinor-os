// LB16 — tagColor tokenisé : les 10 paires de couleurs de pastilles de tag
// vivent dans design/tokens.css (--tag-N-bg/--tag-N-fg, clair+sombre AA) ;
// `tagColor()` garde sa signature ({bg, color}) et renvoie des `var(--tag-N-…)`,
// plus AUCUN hex. Hash déterministe conservé (mêmes buckets qu'avant). Module
// pur → import réel en node --test.
//   node --test src/features/crm/stagesTagColor.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import * as stages from './stages.js'

const { tagColor } = stages

test('LB16 : tagColor renvoie des tokens var(--tag-N-…), jamais de hex', () => {
  for (const tag of ['solaire', 'chaud', 'B2B', 'reda', 'meriem', 'urgent', 'VIP', 'x', '', 'agricole']) {
    const { bg, color } = tagColor(tag)
    assert.match(bg, /^var\(--tag-([1-9]|10)-bg\)$/)
    assert.match(color, /^var\(--tag-([1-9]|10)-fg\)$/)
    assert.doesNotMatch(bg, /#[0-9a-fA-F]/)
    assert.doesNotMatch(color, /#[0-9a-fA-F]/)
  }
})

test('LB16 : le bucket bg et fg d\'un tag partagent le même index N', () => {
  for (const tag of ['solaire', 'B2B', 'urgent', 'meriem']) {
    const { bg, color } = tagColor(tag)
    const nBg = bg.match(/--tag-(\d+)-bg/)[1]
    const nFg = color.match(/--tag-(\d+)-fg/)[1]
    assert.equal(nBg, nFg)
  }
})

test('LB16 : tagColor est déterministe (même tag → même couleur)', () => {
  assert.deepEqual(tagColor('solaire'), tagColor('solaire'))
  assert.deepEqual(tagColor('B2B'), tagColor('B2B'))
})

test('LB16 : aucun hex en sortie, quel que soit le tag, et les 10 buckets restent atteignables', () => {
  // Échantillon large de tags (mots, chiffres, accents, vide, casse) : la
  // palette hex d'origine ne peut plus réapparaître par aucune branche.
  const echantillon = ['', ' ', 'é', 'Å', '0', '12345', 'a'.repeat(40)]
  for (let i = 0; i < 400; i += 1) echantillon.push(`tag-${i}`, `Client ${i * 7}`)
  const buckets = new Set()
  for (const tag of echantillon) {
    const { bg, color } = tagColor(tag)
    assert.doesNotMatch(`${bg} ${color}`, /#[0-9a-fA-F]{3,8}/)
    buckets.add(bg)
  }
  assert.equal(buckets.size, 10)
})

test("LB16 : le module n'exporte plus l'ancienne palette hex (TAG_PALETTE / TAG_TEXT)", () => {
  assert.equal('TAG_PALETTE' in stages, false)
  assert.equal('TAG_TEXT' in stages, false)
  assert.equal(typeof stages.tagColor, 'function')
})
