import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer from './store/messagingSlice'
import useChatPolling, { ACTIVE_POLL_MS } from './useChatPolling'

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
})
