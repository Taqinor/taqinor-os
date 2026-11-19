import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useDeepLinkId } from './useDeepLinkId'

/* Nouveau fichier car : composant neuf, aucun module de test existant pour ce hook.
   Les éléments sont des identifiants seuls : le hook ne lit que `id`. */

const params = (id) => new URLSearchParams(id ? `id=${id}` : '')
const sansEffet = () => {}

describe('useDeepLinkId — objet absent de la liste chargée', () => {
  it('dans la liste : aucune lecture par id', () => {
    const fetchById = vi.fn()
    const { result } = renderHook(() => useDeepLinkId(params(7), sansEffet, [{ id: 7 }], { fetchById }))
    expect(result.current.deepItem).toEqual({ id: 7 })
    expect(result.current.deepLoading).toBe(false)
    expect(fetchById).not.toHaveBeenCalled()
  })

  it('hors de la liste : lu par son id, puis ouvert', async () => {
    const fetchById = vi.fn(() => Promise.resolve({ data: { id: 9, reference: 'CHT-9' } }))
    const { result } = renderHook(() => useDeepLinkId(params(9), sansEffet, [{ id: 1 }], { fetchById }))
    expect(result.current.deepLoading).toBe(true)
    await waitFor(() => expect(result.current.deepItem).toEqual({ id: 9, reference: 'CHT-9' }))
    expect(result.current.deepLoading).toBe(false)
    expect(fetchById).toHaveBeenCalledWith('9')
  })

  it('404 : plus de chargement, aucun objet — l\'appelant dit « introuvable »', async () => {
    const fetchById = vi.fn(() => Promise.reject(new Error('404')))
    const { result } = renderHook(() => useDeepLinkId(params(404), sansEffet, [], { fetchById }))
    await waitFor(() => expect(result.current.deepLoading).toBe(false))
    expect(result.current.deepItem).toBeNull()
  })

  it('liste pas prête : on attend, aucune lecture prématurée', () => {
    const fetchById = vi.fn(() => Promise.resolve({ data: { id: 3 } }))
    renderHook(() => useDeepLinkId(params(3), sansEffet, [], { fetchById, pret: false }))
    expect(fetchById).not.toHaveBeenCalled()
  })

  it('sans fetchById (autres écrans) : comportement inchangé', () => {
    const { result } = renderHook(() => useDeepLinkId(params(5), sansEffet, []))
    expect(result.current.deepItem).toBeNull()
    expect(result.current.deepLoading).toBe(false)
  })
})
