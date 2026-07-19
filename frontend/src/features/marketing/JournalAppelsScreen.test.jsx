import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* WIR161 — un commercial enregistre et consulte un appel depuis l'UI
   (AppelTelephoniqueViewSet, /marketing/appels/ ; company/auteur serveur).
   Réseau mocké. */

const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn() }))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    appels: { list: mocks.list, create: mocks.create },
  },
}))

import JournalAppelsScreen from './JournalAppelsScreen'

const renderScreen = () => render(<MemoryRouter><JournalAppelsScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [
    {
      id: 1, numero: '+212612345678', direction: 'sortant',
      direction_display: 'Sortant', issue: 'repondu', issue_display: 'Répondu',
      note: 'Relance devis', auteur_nom: 'reda', date_appel: '2026-07-19T10:00:00Z',
    },
  ] })
  mocks.create.mockResolvedValue({ data: { id: 2 } })
})

describe('JournalAppelsScreen (WIR161)', () => {
  it('consulte les appels existants du journal', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByText('+212612345678')).toBeTruthy())
    expect(screen.getByText('Relance devis')).toBeTruthy()
    expect(screen.getByText('Sortant')).toBeTruthy()
  })

  it('enregistre un nouvel appel lié à un lead', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())

    fireEvent.click(screen.getByTestId('appels-nouveau'))
    fireEvent.change(screen.getByLabelText('Numéro'), { target: { value: '+212700112233' } })
    fireEvent.change(screen.getByLabelText('Lead / client (id)'), { target: { value: '42' } })
    fireEvent.change(screen.getByLabelText('Issue'), { target: { value: 'rappel' } })

    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({
        numero: '+212700112233', lead_id: 42, direction: 'sortant', issue: 'rappel',
      }),
    ))
  })

  it('exige un numéro avant enregistrement', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('appels-nouveau'))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(screen.getByText('Le numéro est requis.')).toBeTruthy())
    expect(mocks.create).not.toHaveBeenCalled()
  })
})
