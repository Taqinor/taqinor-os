import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* CAD42 — cocher « Récurrent chaque année » sur un Aïd fige cette date
   grégorienne pour toujours, alors qu'une fête lunaire tombe un jour
   différent chaque année. On AVERTIT à la saisie plutôt que de refuser : la
   case reste utilisable, l'utilisateur décide (règle fondateur du 08/09 —
   normaliser ou expliquer, jamais un refus muet). */

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    getRoutingRules: vi.fn(() => Promise.resolve({ data: [] })),
    saveRoutingRule: vi.fn(() => Promise.resolve({ data: {} })),
    deleteRoutingRule: vi.fn(() => Promise.resolve({ data: {} })),
    getWorkingHours: vi.fn(() => Promise.resolve({
      data: { working_days: [0, 1, 2, 3, 4], hours_per_day: 8 },
    })),
    saveWorkingHours: vi.fn(() => Promise.resolve({ data: {} })),
    getHolidays: vi.fn(() => Promise.resolve({ data: [] })),
    createHoliday: vi.fn(() => Promise.resolve({ data: {} })),
    deleteHoliday: vi.fn(() => Promise.resolve({ data: {} })),
    getAnnonces: vi.fn(() => Promise.resolve({ data: [] })),
    createAnnonce: vi.fn(() => Promise.resolve({ data: {} })),
    publierAnnonce: vi.fn(() => Promise.resolve({ data: {} })),
    deleteAnnonce: vi.fn(() => Promise.resolve({ data: {} })),
    getWhatsAppTemplates: vi.fn(() => Promise.resolve({ data: [] })),
    createWhatsAppTemplate: vi.fn(() => Promise.resolve({ data: {} })),
    submitWhatsAppTemplate: vi.fn(() => Promise.resolve({ data: {} })),
    decisionWhatsAppTemplate: vi.fn(() => Promise.resolve({ data: {} })),
    deleteWhatsAppTemplate: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../api/notificationsApi', () => ({ default: apiMock }))

import NotificationsAdminSection from './NotificationsAdminSection'
import { estFerieFixeMa, FERIES_FIXES_MA } from '../../lib/feriesMaroc'

const AVERTISSEMENT = 'cad42-avertissement-recurrent'

async function rendreCalendrier() {
  render(<NotificationsAdminSection />)
  return screen.findByText('Jours fériés')
}

describe('CAD42 — avertir avant de figer une fête lunaire', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('les 9 fériés fixes marocains sont reconnus', () => {
    expect(FERIES_FIXES_MA).toHaveLength(9)
    expect(estFerieFixeMa('2026-05-01')).toBe(true)     // Fête du Travail
    expect(estFerieFixeMa('2027-07-30')).toBe(true)     // Fête du Trône
    expect(estFerieFixeMa('2026-11-18')).toBe(true)     // Indépendance
  })

  it('une date de fête lunaire n’est pas un férié fixe', () => {
    expect(estFerieFixeMa('2026-03-20')).toBe(false)    // Aïd al-Fitr 2026
    expect(estFerieFixeMa('2026-05-27')).toBe(false)    // Aïd al-Adha 2026
    expect(estFerieFixeMa('')).toBe(false)
    expect(estFerieFixeMa(null)).toBe(false)
    expect(estFerieFixeMa('pas une date')).toBe(false)
  })

  it('avertit quand « Récurrent » est coché sur une date hors fériés fixes',
    async () => {
      const user = userEvent.setup()
      await rendreCalendrier()

      // Rien tant que la case n'est pas cochée.
      expect(screen.queryByTestId(AVERTISSEMENT)).toBeNull()

      await user.type(
        screen.getByLabelText('Date du jour férié'), '2026-03-20')
      await user.click(screen.getByLabelText('Récurrent chaque année'))

      await waitFor(() => {
        expect(screen.getByTestId(AVERTISSEMENT)).toBeInTheDocument()
      })
      expect(screen.getByTestId(AVERTISSEMENT))
        .toHaveTextContent('2027')
    })

  it('ne dit rien sur un férié FIXE marqué récurrent', async () => {
    const user = userEvent.setup()
    await rendreCalendrier()

    await user.type(
      screen.getByLabelText('Date du jour férié'), '2026-05-01')
    await user.click(screen.getByLabelText('Récurrent chaque année'))

    await waitFor(() => {
      expect(screen.getByLabelText('Récurrent chaque année'))
        .toHaveAttribute('aria-checked', 'true')
    })
    expect(screen.queryByTestId(AVERTISSEMENT)).toBeNull()
  })
})
