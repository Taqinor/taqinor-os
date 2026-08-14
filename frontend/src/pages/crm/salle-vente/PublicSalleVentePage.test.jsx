import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import api from '../../../api/axios'
import PublicSalleVentePage from './PublicSalleVentePage.jsx'

/* NTCRM18 — page publique de la salle de vente : affiche les items,
   gère mot de passe (403) et expiration (410). */

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn() },
}))

function renderAt(path) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/salle-vente/:token" element={<PublicSalleVentePage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('NTCRM18 PublicSalleVentePage', () => {
  it('affiche les items de la salle', async () => {
    api.get.mockResolvedValue({
      data: {
        titre: 'Ma salle de vente',
        items: [
          { id: 1, type: 'devis', titre: '', reference: 'DV1', total_ttc: '12000.00', proposal_path: '/x' },
          { id: 2, type: 'note', titre: 'Note', reference: 'Bonjour' },
        ],
      },
    })
    renderAt('/salle-vente/tok-1')
    await waitFor(() => expect(screen.getByText('Ma salle de vente')).toBeInTheDocument())
    expect(screen.getByText(/DV1/)).toBeInTheDocument()
    expect(screen.getByText('Bonjour')).toBeInTheDocument()
  })

  it('demande le mot de passe sur 403 puis réessaie', async () => {
    api.get.mockRejectedValueOnce({ response: { status: 403 } })
    api.get.mockResolvedValueOnce({ data: { titre: 'Protégée', items: [] } })

    renderAt('/salle-vente/tok-2')
    await waitFor(() => expect(screen.getByLabelText('Mot de passe')).toBeInTheDocument())

    await userEvent.type(screen.getByLabelText('Mot de passe'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: /Accéder/i }))

    await waitFor(() => expect(screen.getByText('Protégée')).toBeInTheDocument())
  })

  it('affiche un message d\'expiration sur 410', async () => {
    api.get.mockRejectedValue({ response: { status: 410 } })
    renderAt('/salle-vente/tok-3')
    await waitFor(() => expect(screen.getByText(/a expiré/)).toBeInTheDocument())
  })
})
