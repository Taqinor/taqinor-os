import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer from './store/messagingSlice'
import useChatPolling, { ACTIVE_POLL_MS, UNREAD_POLL_MS } from './useChatPolling'

vi.mock('../../api/messagesApi', () => ({
  default: {
    listConversations: vi.fn(() => Promise.resolve({ data: [] })),
    unreadCount: vi.fn(() => Promise.resolve({ data: { total: 0 } })),
    listMessages: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  },
}))

import messagesApi from '../../api/messagesApi'

/* S12 — Le sondage du chat doit se SUSPENDRE quand l'onglet est masqué
   (visibilitychange) et NE PLUS dispatcher tant qu'il l'est. On espionne
   store.dispatch et on pilote document.visibilityState + le temps (fake timers). */

function makeStore() {
  return configureStore({ reducer: { messaging: messagingReducer } })
}

function setVisibility(state) {
  Object.defineProperty(document, 'visibilityState', {
    value: state,
    configurable: true,
  })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('useChatPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('amorce un sondage immédiat puis sonde la conversation active à intervalle', () => {
    const store = makeStore()
    const spy = vi.spyOn(store, 'dispatch')
    const wrapper = ({ children }) => <Provider store={store}>{children}</Provider>
    renderHook(() => useChatPolling(5), { wrapper })

    // Amorçage immédiat (liste + non-lus + messages).
    expect(spy).toHaveBeenCalled()
    const initial = spy.mock.calls.length
    spy.mockClear()

    // Après un tick d'intervalle de la conversation active, un nouveau dispatch.
    vi.advanceTimersByTime(ACTIVE_POLL_MS + 10)
    expect(spy).toHaveBeenCalled()
    expect(initial).toBeGreaterThan(0)
  })

  it('suspend le sondage quand l’onglet devient masqué', () => {
    const store = makeStore()
    const spy = vi.spyOn(store, 'dispatch')
    const wrapper = ({ children }) => <Provider store={store}>{children}</Provider>
    renderHook(() => useChatPolling(5), { wrapper })
    spy.mockClear()

    // Onglet masqué → les intervalles sont coupés.
    setVisibility('hidden')
    spy.mockClear()
    vi.advanceTimersByTime(ACTIVE_POLL_MS * 5)
    expect(spy).not.toHaveBeenCalled()
  })

  it('reprend et rafraîchit immédiatement au retour au premier plan', () => {
    const store = makeStore()
    const spy = vi.spyOn(store, 'dispatch')
    const wrapper = ({ children }) => <Provider store={store}>{children}</Provider>
    renderHook(() => useChatPolling(5), { wrapper })
    setVisibility('hidden')
    spy.mockClear()

    setVisibility('visible')
    // Rafraîchissement immédiat au retour.
    expect(spy).toHaveBeenCalled()
  })

  /* VX204 — aucun `.catch` ne détectait une SÉRIE d'échecs de sondage
     (silence total). ≥3 échecs consécutifs → `stalled`; un succès le lève. */
  describe('détection de panne prolongée (VX204)', () => {
    beforeEach(() => {
      vi.clearAllMocks()
    })

    it('bascule `stalled` à true après 3 échecs consécutifs, false après un succès', async () => {
      messagesApi.unreadCount.mockRejectedValue(new Error('boom'))
      const store = makeStore()
      const wrapper = ({ children }) => <Provider store={store}>{children}</Provider>
      const { result } = renderHook(() => useChatPolling(null, { enabled: true }), { wrapper })

      expect(result.current.stalled).toBe(false)

      // Amorçage immédiat = 1 échec ; 2 ticks d'intervalle supplémentaires = 3.
      await act(async () => { await Promise.resolve() })
      await act(async () => {
        vi.advanceTimersByTime(UNREAD_POLL_MS)
        await Promise.resolve()
      })
      await act(async () => {
        vi.advanceTimersByTime(UNREAD_POLL_MS)
        await Promise.resolve()
      })

      expect(result.current.stalled).toBe(true)

      // Un succès (reprise manuelle) lève l'indicateur.
      messagesApi.unreadCount.mockResolvedValue({ data: { total: 0 } })
      await act(async () => {
        result.current.resume()
        await Promise.resolve()
      })

      expect(result.current.stalled).toBe(false)
    })
  })
})
