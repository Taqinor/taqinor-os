import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import useVisibilityAwarePolling from './useVisibilityAwarePolling'

/* VX56 — Test MIROIR de `features/messaging/useChatPolling.test.jsx` : ce
   hook est le patron partagé extrait de `useChatPolling` (déjà correct) pour
   que `NotificationBell` cesse aussi de sonder un onglet caché. Mêmes
   garanties génériques : amorçage immédiat, suspension sur `visibilitychange`
   → hidden, reprise + rafraîchissement immédiat au retour → visible. */

function setVisibility(state) {
  Object.defineProperty(document, 'visibilityState', {
    value: state,
    configurable: true,
  })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('useVisibilityAwarePolling (VX56)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('amorce un appel immédiat pour chaque tâche puis sonde à sa propre cadence', () => {
    const fnA = vi.fn()
    const fnB = vi.fn()
    renderHook(() => useVisibilityAwarePolling([
      { fn: fnA, intervalMs: 1000 },
      { fn: fnB, intervalMs: 5000 },
    ]))

    // Amorçage immédiat : les deux tâches sont appelées une fois au montage.
    expect(fnA).toHaveBeenCalledTimes(1)
    expect(fnB).toHaveBeenCalledTimes(1)

    // fnA (1s) tique deux fois avant que fnB (5s) ne tique.
    vi.advanceTimersByTime(2000)
    expect(fnA).toHaveBeenCalledTimes(3)
    expect(fnB).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(3000)
    expect(fnB).toHaveBeenCalledTimes(2)
  })

  it('suspend toutes les tâches quand l’onglet devient masqué', () => {
    const fn = vi.fn()
    renderHook(() => useVisibilityAwarePolling([{ fn, intervalMs: 1000 }]))
    fn.mockClear()

    setVisibility('hidden')
    fn.mockClear()
    vi.advanceTimersByTime(10000)
    expect(fn).not.toHaveBeenCalled()
  })

  it('reprend et rafraîchit immédiatement chaque tâche au retour au premier plan', () => {
    const fn = vi.fn()
    renderHook(() => useVisibilityAwarePolling([{ fn, intervalMs: 1000 }]))
    setVisibility('hidden')
    fn.mockClear()

    setVisibility('visible')
    // Rafraîchissement immédiat au retour, avant même le premier tick.
    expect(fn).toHaveBeenCalledTimes(1)

    // Puis reprend son rythme normal.
    fn.mockClear()
    vi.advanceTimersByTime(1000)
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('`resume()` relance immédiatement toutes les tâches à la demande', () => {
    const fnA = vi.fn()
    const fnB = vi.fn()
    const { result } = renderHook(() => useVisibilityAwarePolling([
      { fn: fnA, intervalMs: 60000 },
      { fn: fnB, intervalMs: 60000 },
    ]))
    fnA.mockClear()
    fnB.mockClear()

    result.current.resume()
    expect(fnA).toHaveBeenCalledTimes(1)
    expect(fnB).toHaveBeenCalledTimes(1)
  })

  it('`enabled: false` n’installe aucune tâche', () => {
    const fn = vi.fn()
    renderHook(() => useVisibilityAwarePolling([{ fn, intervalMs: 1000 }], { enabled: false }))
    expect(fn).not.toHaveBeenCalled()
    vi.advanceTimersByTime(5000)
    expect(fn).not.toHaveBeenCalled()
  })
})
