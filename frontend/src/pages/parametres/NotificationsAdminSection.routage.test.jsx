import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* APAR21 — l'écran des règles de routage ne propose QUE les événements
   routables (liste unique du serveur, clé `routable` des préférences) : plus
   de clé tapée à la main (« lead_assigned » serait sans effet). */

const { apiMock } = vi.hoisted(() => {
  const vide = () => Promise.resolve({ data: [] })
  return {
    apiMock: {
      getRoutingRules: vi.fn(vide),
      getPreferences: vi.fn(() => Promise.resolve({ data: [
        { event_type: 'lead_assigned', event_label: 'Lead assigné', routable: false },
        { event_type: 'approval_requested', event_label: 'Approbation demandée', routable: true },
      ] })),
      saveRoutingRule: vi.fn(vide),
      deleteRoutingRule: vi.fn(vide),
      getWorkingHours: vi.fn(() => Promise.resolve({ data: { working_days: 31, hours_per_day: 8 } })),
      saveWorkingHours: vi.fn(vide),
      getHolidays: vi.fn(vide),
      createHoliday: vi.fn(vide),
      deleteHoliday: vi.fn(vide),
      getAnnonces: vi.fn(vide),
      createAnnonce: vi.fn(vide),
      publierAnnonce: vi.fn(vide),
      deleteAnnonce: vi.fn(vide),
      getWhatsAppTemplates: vi.fn(vide),
      createWhatsAppTemplate: vi.fn(vide),
      submitWhatsAppTemplate: vi.fn(vide),
      decisionWhatsAppTemplate: vi.fn(vide),
      deleteWhatsAppTemplate: vi.fn(vide),
    },
  }
})
vi.mock('../../api/notificationsApi', () => ({ default: apiMock }))

import NotificationsAdminSection from './NotificationsAdminSection'

describe('APAR21 — événements routables seulement', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('plus de saisie libre de clé ; seuls les routables sont proposés', async () => {
    render(<NotificationsAdminSection />)
    await waitFor(() => expect(apiMock.getPreferences).toHaveBeenCalled())
    expect(screen.queryByPlaceholderText('lead_assigned')).toBeNull()
    expect(screen.getByRole('combobox', { name: 'Événement' })).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('combobox', { name: 'Événement' }))
    expect(await screen.findByRole('option', { name: 'Approbation demandée' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Lead assigné' })).toBeNull()
  })
})
