import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isTrustedSvg, renderTrustedSvg } from './trustedSvg.js'

// VX120 — le QR 2FA est désormais rendu depuis un SVG produit par NOTRE
// backend (jamais un service tiers), mais on garde une défense en profondeur :
// on refuse tout balisage capable d'exécuter du code avant de l'injecter.

test('isTrustedSvg: accepte un SVG simple (rect/g, comme qr_svg)', () => {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">' +
    '<rect width="10" height="10" fill="#fff"/><g fill="#000">' +
    '<rect x="0" y="0" width="1" height="1"/></g></svg>'
  assert.equal(isTrustedSvg(svg), true)
})

test('isTrustedSvg: refuse une chaîne qui ne commence pas par <svg', () => {
  assert.equal(isTrustedSvg('<div><svg></svg></div>'), false)
})

test('isTrustedSvg: refuse un <script> injecté', () => {
  const svg = '<svg><script>alert(1)</script></svg>'
  assert.equal(isTrustedSvg(svg), false)
})

test('isTrustedSvg: refuse un gestionnaire onload=', () => {
  const svg = '<svg onload="alert(1)"><rect/></svg>'
  assert.equal(isTrustedSvg(svg), false)
})

test('isTrustedSvg: refuse un href javascript:', () => {
  const svg = '<svg><a href="javascript:alert(1)">x</a></svg>'
  assert.equal(isTrustedSvg(svg), false)
})

test('isTrustedSvg: refuse valeurs non-string / vides', () => {
  assert.equal(isTrustedSvg(''), false)
  assert.equal(isTrustedSvg(null), false)
  assert.equal(isTrustedSvg(undefined), false)
  assert.equal(isTrustedSvg(42), false)
})

test('renderTrustedSvg: renvoie {__html} pour un SVG sûr', () => {
  const svg = '<svg><rect/></svg>'
  assert.deepEqual(renderTrustedSvg(svg), { __html: svg })
})

test('renderTrustedSvg: renvoie null pour un SVG suspect', () => {
  assert.equal(renderTrustedSvg('<svg><script>x</script></svg>'), null)
})
