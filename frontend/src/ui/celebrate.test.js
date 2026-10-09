import { describe, it, expect, vi, afterEach } from 'vitest'
import { celebrateDealSigned, PARTY_ID, PARTY_DURATION_MS } from './celebrate'

// Fête « affaire signée » (≥ 30 s, demande fondateur 08/10/2026) : posée
// UNIQUEMENT au passage envoyé→accepté. Rien sous reduced-motion, jamais deux
// fêtes empilées, tout se nettoie à stop().

function mockMatchMedia(reduced) {
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: reduced && query.includes('prefers-reduced-motion'),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }))
}

afterEach(() => {
  document.getElementById(PARTY_ID)?.remove()
  vi.restoreAllMocks()
})

describe('celebrateDealSigned — la fête', () => {
  it('dure plus de 30 secondes', () => {
    expect(PARTY_DURATION_MS).toBeGreaterThan(30000)
  })

  it('stop() retire la scène du DOM', () => {
    mockMatchMedia(false)
    const party = celebrateDealSigned({ sound: false })
    expect(document.getElementById(PARTY_ID)).toBeTruthy()
    party.stop()
    expect(document.getElementById(PARTY_ID)).toBeFalsy()
  })

  it('se monte dans le conteneur fourni (la scène de la carte)', () => {
    mockMatchMedia(false)
    const mount = document.createElement('div')
    document.body.appendChild(mount)
    const party = celebrateDealSigned({ sound: false, mount })
    expect(mount.querySelector(`#${PARTY_ID}`)).toBeTruthy()
    party.stop()
    mount.remove()
  })

  it('pose la scène (canvas) dans le DOM quand le mouvement est autorisé', () => {
    mockMatchMedia(false)
    celebrateDealSigned()
    const el = document.getElementById(PARTY_ID)
    expect(el).toBeTruthy()
    expect(el.children.length).toBeGreaterThan(0)
  })

  it('ne pose RIEN sous prefers-reduced-motion (la carte reste seule)', () => {
    mockMatchMedia(true)
    celebrateDealSigned()
    expect(document.getElementById(PARTY_ID)).toBeFalsy()
  })

  it('ne pile pas une seconde fête si un premier est déjà en cours', () => {
    mockMatchMedia(false)
    celebrateDealSigned()
    const first = document.getElementById(PARTY_ID)
    celebrateDealSigned()
    const all = document.querySelectorAll(`#${PARTY_ID}`)
    expect(all.length).toBe(1)
    expect(all[0]).toBe(first)
  })
})
