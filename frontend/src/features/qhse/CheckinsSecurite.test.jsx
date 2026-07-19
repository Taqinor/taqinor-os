import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR115 — smoke de l'écran Check-ins sécurité + SCAR : il se monte, charge la
   liste des check-ins, et déclenche un check-out via l'action de ligne. */

vi.mock('../../api/qhseApi', () => {
  const checkout = vi.fn(() => Promise.resolve({ data: {} }))
  return {
    default: {
      checkinsSecurite: {
        list: () => Promise.resolve({
          data: [{
            id: 1, technicien_nom: 'Sami T.', site_ref: 'Toiture Anfa',
            heure_checkin: '2026-07-18T08:00:00Z',
            heure_checkout_prevue: '2026-07-18T12:00:00Z',
            heure_checkout_reelle: null, en_retard: false,
          }],
        }),
        create: vi.fn(() => Promise.resolve({ data: {} })),
        checkout,
      },
      demandesActionFournisseur: {
        list: () => Promise.resolve({ data: [] }),
      },
    },
  }
})

import qhseApi from '../../api/qhseApi'
import CheckinsSecurite from './CheckinsSecurite'

const renderScreen = () => render(
  <MemoryRouter>
    <ThemeProvider>
      <CheckinsSecurite />
    </ThemeProvider>
  </MemoryRouter>,
)

beforeEach(() => { qhseApi.checkinsSecurite.checkout.mockClear() })
afterEach(() => cleanup())

describe('WIR115 CheckinsSecurite', () => {
  it('charge et affiche la liste des check-ins', async () => {
    renderScreen()
    // « Sami T. » / « Toiture Anfa » apparaissent en double (vue table + cartes) → All.
    expect((await screen.findAllByText('Sami T.')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Toiture Anfa').length).toBeGreaterThan(0)
  })

  it('déclenche un check-out depuis l’action de ligne', async () => {
    renderScreen()
    await screen.findAllByText('Sami T.')
    // L'action rapide est un IconButton dont le libellé = aria-label (dupliqué table/cartes).
    const btns = await screen.findAllByRole('button', { name: 'Check-out' })
    fireEvent.click(btns[0])
    await waitFor(() =>
      expect(qhseApi.checkinsSecurite.checkout).toHaveBeenCalledWith(1))
  })
})
