import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import DefisPage from './DefisPage'

vi.mock('../../../api/crmApi', () => ({
  default: {
    getDefis: vi.fn(() => Promise.resolve({
      data: {
        results: [
          { id: 1, nom: 'Défi RDV', recompense: 'Dîner au resto' },
          { id: 2, nom: 'Défi leads', recompense: '' },
        ],
      },
    })),
    getDefiClassement: vi.fn((id) => {
      if (id === 1) {
        return Promise.resolve({
          data: [
            { owner_id: 1, owner_nom: 'Sami', realise: 12, rang: 1 },
            { owner_id: 2, owner_nom: 'Meryem', realise: 9, rang: 2 },
            { owner_id: 3, owner_nom: 'Karim', realise: 5, rang: 3 },
            { owner_id: 4, owner_nom: 'Yassine', realise: 2, rang: 4 },
          ],
        })
      }
      return Promise.resolve({ data: [] })
    }),
  },
}))

import crmApi from '../../../api/crmApi'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <DefisPage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('DefisPage (NTCRM24)', () => {
  it('affiche le podium correspondant EXACTEMENT à l\'endpoint classement', async () => {
    mount()
    await waitFor(() => expect(screen.getByTestId('defis-podium')).toBeInTheDocument())
    expect(screen.getByText('Sami')).toBeInTheDocument()
    expect(screen.getByText('Meryem')).toBeInTheDocument()
    expect(screen.getByText('Karim')).toBeInTheDocument()
    // Yassine (4e) n'est pas sur le podium mais dans la liste.
    expect(screen.getByText(/Yassine/)).toBeInTheDocument()
  })

  it('se met à jour au changement de défi sélectionné', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Sami')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Défi leads'))
    await waitFor(() => expect(crmApi.getDefiClassement).toHaveBeenCalledWith(2))
    await waitFor(() => expect(screen.queryByText('Sami')).toBeNull())
  })

  it('affiche un état vide sans défi actif', async () => {
    crmApi.getDefis.mockResolvedValueOnce({ data: { results: [] } })
    mount()
    await waitFor(() => expect(screen.getByText(/Aucun défi actif/)).toBeInTheDocument())
  })
})
