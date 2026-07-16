import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* VX204 — `checkUnread()` (sondage léger toutes les 30 s du compteur de
   notifications) n'avait AUCUNE détection de série d'échecs
   (`.catch(() => {})`, silence total). ≥3 échecs consécutifs doivent afficher
   un indicateur discret « Mise à jour interrompue », levé au premier succès. */

vi.mock('../../api/reportingApi', () => ({
  default: {
    getNotifications: vi.fn(() => Promise.resolve({ data: { total: 0 } })),
    approbationsEnAttente: vi.fn(() => Promise.resolve({ data: { items: [] } })),
  },
}))
vi.mock('../../api/notificationsApi', () => ({
  default: {
    list: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    unreadCount: vi.fn(),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
    attentionSummary: vi.fn(() => Promise.resolve({ data: { approbations: 0 } })),
  },
}))

import notificationsApi from '../../api/notificationsApi'
import NotificationBell from './NotificationBell'

function renderBell() {
  return render(
    <MemoryRouter><NotificationBell /></MemoryRouter>,
  )
}

describe('NotificationBell — panne prolongée du sondage léger (VX204)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('affiche « Mise à jour interrompue » après 3 échecs consécutifs, la lève après un succès', async () => {
    notificationsApi.unreadCount.mockRejectedValue(new Error('boom'))
    renderBell()

    // Ouvrir la cloche pour voir le panneau.
    fireEvent.click(screen.getByRole('button', { name: /Notifications/ }))

    // Amorçage immédiat (1er échec) + 2 ticks d'intervalle (30s) => 3 échecs.
    await act(async () => { await Promise.resolve() })
    await act(async () => {
      vi.advanceTimersByTime(30 * 1000)
      await Promise.resolve()
    })
    await act(async () => {
      vi.advanceTimersByTime(30 * 1000)
      await Promise.resolve()
    })

    expect(screen.getByText(/Mise à jour interrompue/)).toBeInTheDocument()

    // Reprise manuelle : un succès lève l'indicateur.
    notificationsApi.unreadCount.mockResolvedValue({ data: { unread: 0 } })
    await act(async () => {
      fireEvent.click(screen.getByText(/Mise à jour interrompue/))
      await Promise.resolve()
    })

    expect(screen.queryByText(/Mise à jour interrompue/)).not.toBeInTheDocument()
  })
})
