import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, waitFor, cleanup } from '@testing-library/react'
import { useEquipeMembreIds } from './useEquipeMembreIds'

// VX236 — résout `?equipe=<id>` en l'ensemble des membres de cette équipe,
// pour un filtre client-side (leads/devis) — aucun endpoint nouveau,
// `crmApi.getEquipes()` (déjà existant) suffit.

vi.mock('../api/crmApi', () => ({
  default: {
    getEquipes: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, nom: 'Nord', membres: [10, 11] },
        { id: 2, nom: 'Sud', membres: [20] },
      ],
    })),
  },
}))

import crmApi from '../api/crmApi'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('VX236 — useEquipeMembreIds', () => {
  it('sans équipeId : retourne null (aucun filtre), aucun appel réseau', () => {
    const { result } = renderHook(() => useEquipeMembreIds(null))
    expect(result.current).toBe(null)
    expect(crmApi.getEquipes).not.toHaveBeenCalled()
  })

  it('résout les membres de l’équipe demandée', async () => {
    const { result } = renderHook(() => useEquipeMembreIds('1'))
    await waitFor(() => expect(result.current).not.toBe(null))
    expect(result.current.has(10)).toBe(true)
    expect(result.current.has(11)).toBe(true)
    expect(result.current.has(20)).toBe(false)
  })

  it('équipe introuvable : Set vide (jamais un filtre qui plante)', async () => {
    const { result } = renderHook(() => useEquipeMembreIds('999'))
    await waitFor(() => expect(result.current).not.toBe(null))
    expect(result.current.size).toBe(0)
  })
})
