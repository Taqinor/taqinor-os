import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* APAR19 — la colonne WhatsApp des préférences est grisée « non disponible »
   tant qu'aucun transport n'existe : aucune case cochable, même si la
   préférence stockée est à true (elle n'est pas effacée). */

vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

vi.mock('../../api/notificationsApi', () => ({
  default: {
    getPreferences: () => Promise.resolve({ data: [
      { event_type: 'lead_assigned', event_label: 'Lead assigné', in_app: true, whatsapp: true, email: false, push: true },
    ] }),
    savePreference: vi.fn(() => Promise.resolve({ data: {} })),
    getVapidKey: () => Promise.resolve({ data: {} }),
  },
}))
vi.mock('../../features/pwa/pushSubscribe', () => ({
  pushSupported: () => false,
  subscribeToPush: vi.fn(),
  unsubscribeFromPush: vi.fn(),
}))

import NotificationsPreferences from './NotificationsPreferences'

describe('APAR19 — WhatsApp non disponible', () => {
  afterEach(cleanup)

  it('la case WhatsApp est désactivée et décochée, les autres restent actives', async () => {
    render(<MemoryRouter><NotificationsPreferences /></MemoryRouter>)
    const wa = await screen.findByRole('switch', { name: /Lead assigné — WhatsApp \(non disponible\)/ })
    expect(wa).toBeDisabled()
    expect(wa).toHaveAttribute('aria-checked', 'false')
    const inApp = screen.getByRole('switch', { name: 'Lead assigné — In-app' })
    expect(inApp).not.toBeDisabled()
    expect(screen.getByRole('columnheader', { name: /WhatsApp/ }))
      .toHaveAttribute('title', expect.stringMatching(/Non disponible/))
  })
})
