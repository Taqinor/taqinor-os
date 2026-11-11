import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* ATST11 (C-ATST-028) — « Régénérer le lien » iCal JOUÉ sur l'écran rendu
   (plus une regex sur le source) : rougit sur `if (!ok) return` →
   `if (ok) return` et sur `setSubUrl('')`. */

vi.mock('../api/reportingApi', () => ({
  default: {
    getCalendar: vi.fn(),
    getCalendarSubscription: vi.fn(),
    regenererCalendarSubscription: vi.fn(),
    rescheduleCalendar: vi.fn(),
  },
}))
vi.mock('../api/crmApi', () => ({ default: { getAssignableUsers: vi.fn() } }))

import reportingApi from '../api/reportingApi'
import crmApi from '../api/crmApi'
import CalendarPage from './CalendarPage'
import { ThemeProvider } from '../design/ThemeProvider'
import { ConfirmProvider } from '../providers/ConfirmProvider'

const ANCIEN = 'https://erp.example.invalid/ics/ancien'
const NOUVEAU = 'https://erp.example.invalid/ics/nouveau'

async function ouvrirAbonnement(user) {
  render(
    <MemoryRouter>
      <ThemeProvider>
        <ConfirmProvider>
          <CalendarPage />
        </ConfirmProvider>
      </ThemeProvider>
    </MemoryRouter>,
  )
  await user.click(screen.getByRole('button', { name: "S'abonner au calendrier" }))
  const champ = screen.getByPlaceholderText('Génération du lien…')
  await waitFor(() => expect(champ).toHaveValue(ANCIEN))
  return champ
}

async function regenerer(user, bouton) {
  await user.click(screen.getByRole('button', { name: 'Régénérer le lien' }))
  const dialogue = await screen.findByRole('alertdialog')
  await user.click(within(dialogue).getByRole('button', { name: bouton }))
}

beforeEach(() => {
  vi.clearAllMocks()
  reportingApi.getCalendar.mockResolvedValue({ data: { events: [] } })
  reportingApi.getCalendarSubscription.mockResolvedValue({ data: { url: ANCIEN } })
  reportingApi.regenererCalendarSubscription.mockResolvedValue({ data: { url: NOUVEAU } })
  crmApi.getAssignableUsers.mockResolvedValue({ data: [] })
})

describe('ATST11 — CalendarPage : régénérer le lien d’abonnement', () => {
  // Une ouverture de boîte par test (réouverture instable sous jsdom/Radix).
  it('annuler la confirmation ne régénère rien : l’ancien lien reste', async () => {
    const user = userEvent.setup()
    const champ = await ouvrirAbonnement(user)
    await regenerer(user, 'Annuler')
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(reportingApi.regenererCalendarSubscription).not.toHaveBeenCalled()
    expect(champ).toHaveValue(ANCIEN)
  })

  it('confirmer régénère une fois et affiche la nouvelle URL', async () => {
    const user = userEvent.setup()
    const champ = await ouvrirAbonnement(user)
    await regenerer(user, 'Régénérer')
    await waitFor(() => expect(champ).toHaveValue(NOUVEAU))
    expect(reportingApi.regenererCalendarSubscription).toHaveBeenCalledTimes(1)
  })

  it('une régénération refusée affiche « Régénération du lien impossible. »', async () => {
    reportingApi.regenererCalendarSubscription.mockRejectedValue(new Error('500'))
    const user = userEvent.setup()
    await ouvrirAbonnement(user)
    await regenerer(user, 'Régénérer')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Régénération du lien impossible.')
  })
})
