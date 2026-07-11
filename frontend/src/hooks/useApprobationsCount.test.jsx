import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

/* VX86 — Hook partagé de comptage des approbations en attente (source unique
   pour le badge nav Sidebar, la carte Dashboard « Attend votre décision » et
   la rangée cloche). Vérifie : total dérivé de `items.length`, masquage à 0/
   erreur pendant le chargement, et bascule propre sur erreur réseau. */

const approbationsEnAttenteMock = vi.fn()
vi.mock('../api/reportingApi', () => ({
  default: { approbationsEnAttente: (...args) => approbationsEnAttenteMock(...args) },
}))

import { useApprobationsCount } from './useApprobationsCount'

describe('useApprobationsCount (VX86)', () => {
  beforeEach(() => {
    approbationsEnAttenteMock.mockReset()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('démarre à 0 en chargement', () => {
    approbationsEnAttenteMock.mockReturnValue(new Promise(() => {})) // jamais résolu
    const { result } = renderHook(() => useApprobationsCount())
    expect(result.current.loading).toBe(true)
    expect(result.current.total).toBe(0)
    expect(result.current.error).toBe(false)
  })

  it('expose le total = nombre d’items renvoyés par la boîte unfiltrée', async () => {
    approbationsEnAttenteMock.mockResolvedValue({
      data: { items: [{ id: 1, source: 'workflow' }, { id: 2, source: 'ged' }] },
    })
    const { result } = renderHook(() => useApprobationsCount())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.total).toBe(2)
    expect(result.current.error).toBe(false)
  })

  it('reste à 0 (jamais un total inventé) quand la boîte est vide', async () => {
    approbationsEnAttenteMock.mockResolvedValue({ data: { items: [] } })
    const { result } = renderHook(() => useApprobationsCount())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.total).toBe(0)
  })

  it('bascule error=true sur échec réseau, sans casser le total à une valeur inventée', async () => {
    approbationsEnAttenteMock.mockRejectedValue(new Error('network'))
    const { result } = renderHook(() => useApprobationsCount())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe(true)
    expect(result.current.total).toBe(0)
  })
})
