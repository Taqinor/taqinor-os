// NTUX12 — useFavoris : source unique consommée par FavoriButton (bouton
// étoile) et FavorisWidget (liste sidebar/dashboard).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'

const listFavorisMock = vi.fn()
const createFavoriMock = vi.fn()
const deleteFavoriMock = vi.fn()
const reordonnerFavoriMock = vi.fn()
vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listFavoris: (...a) => listFavorisMock(...a),
    createFavori: (...a) => createFavoriMock(...a),
    deleteFavori: (...a) => deleteFavoriMock(...a),
    reordonnerFavori: (...a) => reordonnerFavoriMock(...a),
  },
}))

import { useFavoris } from './useFavoris'

const FAVORIS = [
  { id: 1, modele: 'installations.installation', object_id: 7, libelle: 'Chantier Nouaceur', ordre: 0 },
  { id: 2, modele: 'crm.lead', object_id: 3, libelle: 'Ali Ben', ordre: 1 },
]

beforeEach(() => {
  listFavorisMock.mockReset().mockResolvedValue({ data: FAVORIS })
  createFavoriMock.mockReset().mockResolvedValue({ data: { id: 3 } })
  deleteFavoriMock.mockReset().mockResolvedValue({ data: {} })
  reordonnerFavoriMock.mockReset().mockResolvedValue({ data: FAVORIS })
})

describe('useFavoris (NTUX12)', () => {
  it('charge les favoris au montage', async () => {
    const { result } = renderHook(() => useFavoris())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.favoris).toEqual(FAVORIS)
  })

  it('isFavori détecte une cible déjà épinglée, insensible au type (string vs number) de object_id', async () => {
    const { result } = renderHook(() => useFavoris())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.isFavori('installations.installation', 7)).toBe(true)
    expect(result.current.isFavori('installations.installation', '7')).toBe(true)
    expect(result.current.isFavori('crm.lead', 999)).toBe(false)
  })

  it('toggle sur une cible NON épinglée : POST create puis recharge', async () => {
    const { result } = renderHook(() => useFavoris())
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(async () => { await result.current.toggle('crm.devis', 42) })
    expect(createFavoriMock).toHaveBeenCalledWith('crm.devis', 42)
    expect(deleteFavoriMock).not.toHaveBeenCalled()
    expect(listFavorisMock.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('toggle sur une cible DÉJÀ épinglée : DELETE avec le bon id de favori', async () => {
    const { result } = renderHook(() => useFavoris())
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(async () => { await result.current.toggle('crm.lead', 3) })
    expect(deleteFavoriMock).toHaveBeenCalledWith(2)
    expect(createFavoriMock).not.toHaveBeenCalled()
  })

  it('reorder persiste et adopte immédiatement la liste renvoyée par le serveur', async () => {
    const reordered = [FAVORIS[1], FAVORIS[0]]
    reordonnerFavoriMock.mockResolvedValueOnce({ data: reordered })
    const { result } = renderHook(() => useFavoris())
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(async () => { await result.current.reorder(2, 0) })
    expect(reordonnerFavoriMock).toHaveBeenCalledWith(2, 0)
    expect(result.current.favoris).toEqual(reordered)
  })

  it('échec de chargement : erreur explicite, liste vide (jamais un crash)', async () => {
    listFavorisMock.mockReset().mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useFavoris())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.favoris).toEqual([])
    expect(result.current.error).toBeTruthy()
  })
})
