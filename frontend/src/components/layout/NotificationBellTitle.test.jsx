import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* VX82 — NotificationBell préfixe `(N)` le titre d'onglet quand des
   notifications sont non lues, et le retire dès que le compteur retombe à
   zéro — sans jamais toucher au reste du titre (posé par ailleurs via
   useDocumentTitle sur chaque page). */

const getNotifications = vi.fn()
vi.mock('../../api/reportingApi', () => ({
  default: {
    getNotifications: (...args) => getNotifications(...args),
    approbationsEnAttente: vi.fn(() => Promise.resolve({ data: { items: [] } })),
  },
}))
vi.mock('../../api/notificationsApi', () => ({
  default: {
    list: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    unreadCount: vi.fn(() => Promise.resolve({ data: { unread: 0 } })),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
    attentionSummary: vi.fn(() => Promise.resolve({ data: { approbations: 0 } })),
  },
}))

import NotificationBell from './NotificationBell'

function renderBell() {
  return render(
    <MemoryRouter><NotificationBell /></MemoryRouter>,
  )
}

describe('NotificationBell — préfixe (N) du titre d’onglet (VX82)', () => {
  const originalTitle = document.title
  beforeEach(() => {
    vi.useFakeTimers()
    document.title = 'Devis · TAQINOR'
  })
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.restoreAllMocks()
    document.title = originalTitle
  })

  it('pose le préfixe (N) quand il y a des notifications non lues', async () => {
    getNotifications.mockResolvedValue({ data: { total: 3 } })
    renderBell()
    await act(async () => { await Promise.resolve() })
    await act(async () => { await vi.runOnlyPendingTimersAsync() })
    expect(document.title).toBe('(3) Devis · TAQINOR')
  })

  it('ne pose aucun préfixe quand tout est lu (total = 0)', async () => {
    getNotifications.mockResolvedValue({ data: { total: 0 } })
    renderBell()
    await act(async () => { await Promise.resolve() })
    await act(async () => { await vi.runOnlyPendingTimersAsync() })
    expect(document.title).toBe('Devis · TAQINOR')
  })

  it('retire le préfixe une fois retombé à zéro (ne laisse pas de résidu)', async () => {
    getNotifications.mockResolvedValueOnce({ data: { total: 2 } })
    renderBell()
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(document.title).toBe('(2) Devis · TAQINOR')

    // Le rafraîchissement suivant (3 min) retombe à 0.
    getNotifications.mockResolvedValueOnce({ data: { total: 0 } })
    await act(async () => {
      vi.advanceTimersByTime(3 * 60 * 1000)
      await Promise.resolve()
    })
    await act(async () => { await vi.runOnlyPendingTimersAsync() })
    expect(document.title).toBe('Devis · TAQINOR')
  })
})
