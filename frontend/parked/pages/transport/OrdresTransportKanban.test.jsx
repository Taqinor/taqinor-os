import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* NTLOG25 — kanban des ordres de transport par statut. Le glisser-déposer
   dnd-kit n'est pas simulable proprement en jsdom : le bouton « Marquer
   livré » de chaque carte appelle EXACTEMENT la même action serveur que le
   dépôt sur la colonne « Livré » (`etapes-transport/{id}/livrer/`) — on
   exerce donc le garde-fou POD obligatoire (NTLOG9) via ce bouton, qui
   couvre le même code de blocage que le drop. */

const { post } = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { post } }))

const { toastError, toastSuccess, toastInfo } = vi.hoisted(() => ({
  toastError: vi.fn(), toastSuccess: vi.fn(), toastInfo: vi.fn(),
}))
vi.mock('../../ui/confirm', () => ({
  toast: { error: toastError, success: toastSuccess, info: toastInfo },
}))

import OrdresTransportKanban from './OrdresTransportKanban'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const ORDRE_PLANIFIE = {
  id: 1, numero: 'OT-2026-0001', statut: 'planifie',
  destinataire_nom: 'Client A', mode_transport_display: 'Affrètement',
  poids_total_kg: '120.00', date_livraison_prevue: '2026-08-20',
  etapes: [
    { id: 11, type_etape: 'livraison', date_prevue: '2026-08-20', date_reelle: null },
  ],
}

describe('OrdresTransportKanban', () => {
  it('range chaque ordre dans la colonne de son statut', () => {
    render(<OrdresTransportKanban ordres={[ORDRE_PLANIFIE]} />)
    expect(screen.getByText('OT-2026-0001')).toBeInTheDocument()
    expect(screen.getByText('Client A')).toBeInTheDocument()
  })

  it('bloque la clôture de livraison sans POD avec un message explicite (NTLOG9)', async () => {
    post.mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Photo ou signature requise avant de clôturer la livraison.' } },
    })
    const user = userEvent.setup()
    render(<OrdresTransportKanban ordres={[ORDRE_PLANIFIE]} />)

    await user.click(screen.getByRole('button', { name: 'Marquer livré' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/transport/etapes-transport/11/livrer/',
    ))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith(
      'Photo ou signature requise avant de clôturer la livraison.',
    ))
    expect(toastSuccess).not.toHaveBeenCalled()
  })

  it('confirme la livraison quand le POD est déjà déposé', async () => {
    post.mockResolvedValueOnce({ data: {} })
    const onChanged = vi.fn()
    const user = userEvent.setup()
    render(<OrdresTransportKanban ordres={[ORDRE_PLANIFIE]} onChanged={onChanged} />)

    await user.click(screen.getByRole('button', { name: 'Marquer livré' }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Ordre livré.'))
    expect(onChanged).toHaveBeenCalled()
  })

  it("affiche un indicateur de retard quand la date réelle dépasse la date prévue", () => {
    const ordreEnRetard = {
      ...ORDRE_PLANIFIE,
      id: 2,
      etapes: [{ id: 12, type_etape: 'livraison', date_prevue: '2026-08-10', date_reelle: '2026-08-15' }],
    }
    render(<OrdresTransportKanban ordres={[ordreEnRetard]} />)
    expect(screen.getByText('Retard')).toBeInTheDocument()
  })
})
