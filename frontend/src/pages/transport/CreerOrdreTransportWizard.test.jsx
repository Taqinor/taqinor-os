import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* NTLOG32 — wizard "Créer un ordre de transport" en 3 étapes. Critère
   d'acceptation : abandonner le wizard à l'étape 2 ne crée AUCUN
   enregistrement partiel — vérifié ici en s'assurant qu'aucun appel réseau
   n'a lieu tant que l'utilisateur n'a pas atteint le bouton final « Créer
   l'ordre » à l'étape 3. */

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { get, post } }))

const { toastError, toastSuccess } = vi.hoisted(() => ({
  toastError: vi.fn(), toastSuccess: vi.fn(),
}))
vi.mock('../../ui/confirm', () => ({
  toast: { error: toastError, success: toastSuccess },
  confirmLeaveIfDirty: () => true,
}))

import CreerOrdreTransportWizard from './CreerOrdreTransportWizard'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function withRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('CreerOrdreTransportWizard', () => {
  it("n'appelle AUCUNE création tant que l'étape finale n'est pas confirmée", async () => {
    const user = userEvent.setup()
    withRouter(<CreerOrdreTransportWizard />)

    // Étape 1 -> 2 (mode transport, charge le comparateur NTLOG7).
    get.mockResolvedValueOnce({ data: [] })
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await waitFor(() => expect(get).toHaveBeenCalledWith('/installations/transporteurs/'))

    // Abandon à l'étape 2 : aucun POST n'a jamais été émis.
    expect(post).not.toHaveBeenCalled()
  })

  it("crée l'ordre puis ses lignes/étapes en séquence au clic final", async () => {
    const user = userEvent.setup()
    get.mockResolvedValueOnce({ data: [] })
    post.mockImplementation((url) => {
      if (url === '/transport/ordres-transport/') {
        return Promise.resolve({ data: { id: 42, numero: 'OT-2026-0042' } })
      }
      return Promise.resolve({ data: { id: 1 } })
    })

    withRouter(<CreerOrdreTransportWizard />)

    await user.type(screen.getByPlaceholderText('Désignation'), 'Panneau solaire')
    await user.type(screen.getByPlaceholderText('Poids (kg)'), '25')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await waitFor(() => expect(get).toHaveBeenCalled())
    await user.click(screen.getByRole('button', { name: 'Suivant' }))

    await user.click(screen.getByRole('button', { name: "Créer l'ordre" }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/transport/ordres-transport/', expect.objectContaining({ mode_transport: 'affretement' }),
    ))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/transport/lignes-transport/',
      expect.objectContaining({ ordre: 42, designation: 'Panneau solaire' }),
    ))
    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/transport/etapes-transport/',
      expect.objectContaining({ ordre: 42, type_etape: 'enlevement' }),
    ))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled())
  })
})
