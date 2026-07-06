import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import gedApi from '../../api/gedApi'
import PublicDepotPage from './PublicDepotPage.jsx'

/* XGED7 — dépôt public : consulter le lien → déposer un fichier. */

vi.mock('../../api/gedApi', () => ({
  default: {
    getDepotPublic: vi.fn(),
    deposerPublique: vi.fn(),
  },
}))

function renderAt(path) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/ged/depot/:token" element={<PublicDepotPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('XGED7 PublicDepotPage', () => {
  it('affiche le message et dépose un fichier', async () => {
    gedApi.getDepotPublic.mockResolvedValue({
      data: { message: 'Merci d’envoyer votre attestation.', quota_fichiers_restant: 2 },
    })
    gedApi.deposerPublique.mockResolvedValue({ data: { document: 5 } })

    renderAt('/ged/depot/dep-1')
    await waitFor(() =>
      expect(screen.getByText(/attestation/i)).toBeInTheDocument())

    const file = new File(['x'], 'piece.pdf', { type: 'application/pdf' })
    await userEvent.upload(screen.getByLabelText(/Fichier/i), file)
    await userEvent.click(screen.getByRole('button', { name: /Déposer/i }))

    await waitFor(() =>
      expect(gedApi.deposerPublique).toHaveBeenCalledWith(
        'dep-1', expect.objectContaining({ file })))
    await waitFor(() =>
      expect(screen.getByText(/bien été déposé/i)).toBeInTheDocument())
  })

  it('affiche un message honnête sur un lien invalide', async () => {
    gedApi.getDepotPublic.mockRejectedValue({ response: { status: 404 } })
    renderAt('/ged/depot/bad')
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/introuvable|expiré/i))
  })
})
