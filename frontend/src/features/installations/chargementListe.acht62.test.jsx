// ACHT62 — `useFilteredList` (Approvisionnement 6 onglets, Suivi GPS alertes,
// kits, import) lit TOUTES les pages d'un faux serveur DRF paginé à 50.
import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useFilteredList } from './chargementListe'

const PAGE_SIZE = 50
const serveur = (total) => {
  const lignes = Array.from({ length: total }, (_, i) => ({ id: i + 1 }))
  return ({ page = 1 } = {}) => {
    const debut = (page - 1) * PAGE_SIZE
    return Promise.resolve({
      data: {
        count: total,
        next: debut + PAGE_SIZE < total ? `?page=${page + 1}` : null,
        results: lignes.slice(debut, debut + PAGE_SIZE),
      },
    })
  }
}

describe('useFilteredList — ACHT62', () => {
  it('rend les 51 lignes d’une liste paginée à 50', async () => {
    const fetcher = serveur(51)
    const { result } = renderHook(() => useFilteredList(fetcher))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.rows).toHaveLength(51)
  })

  it('une liste nue (endpoint non paginé) reste intacte', async () => {
    const fetcher = () => Promise.resolve({ data: [{ id: 1 }, { id: 2 }] })
    const { result } = renderHook(() => useFilteredList(fetcher))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.rows).toHaveLength(2)
  })
})
