import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDraftAutosave } from './useDraftAutosave'

/* VX62 — Brouillon auto du générateur de devis.
   On vérifie : saisie débouncée → localStorage écrit ; un remontage relit le
   brouillon (« Reprendre ») ; restore() rend le payload ; clear()/discard()
   purgent la clé ; un localStorage indisponible ne casse jamais le hook. */
describe('useDraftAutosave (VX62)', () => {
  const KEY = 'devis:new'
  const STORAGE_KEY = 'taqinor:draft:devis:new'

  beforeEach(() => {
    vi.useFakeTimers()
    window.localStorage.clear()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('écrit le snapshot dans localStorage après le debounce (800 ms)', () => {
    const { rerender } = renderHook(
      ({ snap }) => useDraftAutosave(KEY, snap, { enabled: true }),
      { initialProps: { snap: { note: 'a' } } },
    )
    // Rien tout de suite.
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    // Nouvelle frappe puis attente du debounce.
    rerender({ snap: { note: 'ab' } })
    act(() => { vi.advanceTimersByTime(800) })
    const raw = JSON.parse(window.localStorage.getItem(STORAGE_KEY))
    expect(raw.data).toEqual({ note: 'ab' })
    expect(typeof raw.savedAt).toBe('string')
  })

  it('n’écrit rien tant que enabled est faux (formulaire vierge)', () => {
    renderHook(() => useDraftAutosave(KEY, { note: 'x' }, { enabled: false }))
    act(() => { vi.advanceTimersByTime(1000) })
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('relit un brouillon existant au montage et le restaure via restore()', () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ savedAt: '2026-07-11T10:00:00Z', data: { note: 'repris', nbPanneaux: '8' } }),
    )
    const { result } = renderHook(() => useDraftAutosave(KEY, {}, { enabled: false }))
    expect(result.current.restored).not.toBeNull()
    expect(result.current.restored.data.note).toBe('repris')
    let payload
    act(() => { payload = result.current.restore() })
    expect(payload).toEqual({ note: 'repris', nbPanneaux: '8' })
    // Après restore, le bandeau disparaît.
    expect(result.current.restored).toBeNull()
  })

  it('discard() purge la clé et masque le bandeau', () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ savedAt: '2026-07-11T10:00:00Z', data: { note: 'z' } }),
    )
    const { result } = renderHook(() => useDraftAutosave(KEY, {}, { enabled: false }))
    act(() => { result.current.discard() })
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    expect(result.current.restored).toBeNull()
  })

  it('clear() vide la clé (appelé après un submit réussi)', () => {
    const { result, rerender } = renderHook(
      ({ snap }) => useDraftAutosave(KEY, snap, { enabled: true }),
      { initialProps: { snap: { note: 'a' } } },
    )
    rerender({ snap: { note: 'ab' } })
    act(() => { vi.advanceTimersByTime(800) })
    expect(window.localStorage.getItem(STORAGE_KEY)).not.toBeNull()
    act(() => { result.current.clear() })
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('ne casse jamais si localStorage lève (Safari privé / quota)', () => {
    const spy = vi.spyOn(window.localStorage.__proto__, 'setItem')
      .mockImplementation(() => { throw new Error('QuotaExceededError') })
    const { rerender } = renderHook(
      ({ snap }) => useDraftAutosave(KEY, snap, { enabled: true }),
      { initialProps: { snap: { note: 'a' } } },
    )
    expect(() => {
      rerender({ snap: { note: 'ab' } })
      act(() => { vi.advanceTimersByTime(800) })
    }).not.toThrow()
    spy.mockRestore()
  })
})
