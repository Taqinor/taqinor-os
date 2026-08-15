// NTMOB33 — aide contextuelle terrain (logique pure : drapeau par utilisateur).
import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  ETAPES, cleOnboarding, doitAfficherOnboarding, marquerOnboardingVu,
} from './aideTerrain.js'

function fauxLocalStorage() {
  const data = new Map()
  return {
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => data.set(k, String(v)),
  }
}

beforeEach(() => { globalThis.window = { localStorage: fauxLocalStorage() } })

test('NTMOB33: exactement 3 étapes', () => {
  assert.equal(ETAPES.length, 3)
})

test('NTMOB33: affichée une seule fois, puis plus jamais', () => {
  assert.equal(doitAfficherOnboarding(7), true)
  marquerOnboardingVu(7)
  assert.equal(doitAfficherOnboarding(7), false)
})

test('NTMOB33: le drapeau est PAR utilisateur (téléphone partagé)', () => {
  marquerOnboardingVu(7)
  assert.equal(doitAfficherOnboarding(8), true)
  assert.notEqual(cleOnboarding(7), cleOnboarding(8))
})

test('NTMOB33: stockage indisponible = pas d\'affichage en boucle', () => {
  globalThis.window = {
    get localStorage() { throw new Error('mode privé') },
  }
  assert.equal(doitAfficherOnboarding(7), false)
  assert.doesNotThrow(() => marquerOnboardingVu(7))
})
