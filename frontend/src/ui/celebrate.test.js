import { describe, it, expect, vi, afterEach } from 'vitest'
import { celebrateDealSigned } from './celebrate'

// VX40 — Le délice mesuré : célébration UNIQUE au passage envoyé→accepté.
// Statique sous reduced-motion = RIEN posé dans le DOM (l'appelant garde son
// toast.success habituel, seul retour visuel). Jamais deux bursts empilés.

function mockMatchMedia(reduced) {
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: reduced && query.includes('prefers-reduced-motion'),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }))
}

afterEach(() => {
  document.getElementById('vx40-deal-signed-burst')?.remove()
  vi.restoreAllMocks()
})

describe('celebrateDealSigned (VX40)', () => {
  it('pose un burst CSS-only dans le DOM quand le mouvement est autorisé', () => {
    mockMatchMedia(false)
    celebrateDealSigned()
    const el = document.getElementById('vx40-deal-signed-burst')
    expect(el).toBeTruthy()
    expect(el.children.length).toBeGreaterThan(0)
  })

  it('ne pose RIEN sous prefers-reduced-motion (toast seul)', () => {
    mockMatchMedia(true)
    celebrateDealSigned()
    expect(document.getElementById('vx40-deal-signed-burst')).toBeFalsy()
  })

  it('ne pile pas un second burst si un premier est déjà en cours', () => {
    mockMatchMedia(false)
    celebrateDealSigned()
    const first = document.getElementById('vx40-deal-signed-burst')
    celebrateDealSigned()
    const all = document.querySelectorAll('#vx40-deal-signed-burst')
    expect(all.length).toBe(1)
    expect(all[0]).toBe(first)
  })
})
