// NTUX12 — bouton étoile générique, drop-in sur n'importe quel écran de
// détail. Couvre : rendu conditionnel (pas d'id → rien), état épinglé/non
// épinglé, le toggle appelle bien create/delete, et l'échec serveur toast au
// lieu de crasher.
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const listFavorisMock = vi.fn()
const createFavoriMock = vi.fn()
const deleteFavoriMock = vi.fn()
vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listFavoris: (...a) => listFavorisMock(...a),
    createFavori: (...a) => createFavoriMock(...a),
    deleteFavori: (...a) => deleteFavoriMock(...a),
    reordonnerFavori: vi.fn(),
  },
}))

const toastError = vi.fn()
vi.mock('../../ui/confirm', () => ({ toast: { error: (...a) => toastError(...a) } }))

import FavoriButton from './FavoriButton'

beforeEach(() => {
  listFavorisMock.mockReset().mockResolvedValue({ data: [] })
  createFavoriMock.mockReset().mockResolvedValue({ data: { id: 1 } })
  deleteFavoriMock.mockReset().mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('FavoriButton — NTUX12', () => {
  it('sans objectId : ne rend rien (jamais une étoile cassée)', () => {
    const { container } = render(<FavoriButton modele="crm.lead" objectId={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('cible non épinglée : libellé « Épingler aux favoris », clic → createFavori', async () => {
    const user = userEvent.setup()
    render(<FavoriButton modele="installations.installation" objectId={7} />)
    const btn = await screen.findByRole('button', { name: 'Épingler aux favoris' })
    await user.click(btn)
    await waitFor(() => expect(createFavoriMock).toHaveBeenCalledWith('installations.installation', 7))
  })

  it('cible déjà épinglée : libellé « Retirer des favoris », clic → deleteFavori', async () => {
    listFavorisMock.mockResolvedValue({
      data: [{ id: 5, modele: 'crm.lead', object_id: 3, libelle: 'Ali' }],
    })
    const user = userEvent.setup()
    render(<FavoriButton modele="crm.lead" objectId={3} />)
    const btn = await screen.findByRole('button', { name: 'Retirer des favoris' })
    await user.click(btn)
    await waitFor(() => expect(deleteFavoriMock).toHaveBeenCalledWith(5))
  })

  it('échec serveur (ex. limite NTUX28) : toast avec le detail, jamais un crash', async () => {
    createFavoriMock.mockRejectedValue({ response: { data: { detail: 'Limite de 30 favoris atteinte.' } } })
    const user = userEvent.setup()
    render(<FavoriButton modele="crm.lead" objectId={9} />)
    const btn = await screen.findByRole('button', { name: 'Épingler aux favoris' })
    await user.click(btn)
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('Limite de 30 favoris atteinte.'))
  })
})
