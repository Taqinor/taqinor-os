import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

/* VX86 — Hook partagé de comptage des approbations en attente (source unique
   pour le badge nav Sidebar, la carte Dashboard « Attend votre décision » et
   la rangée cloche). VX207 — source désormais l'endpoint canonique unique
   `notificationsApi.attentionSummary()` (champ `approbations`). Vérifie : total
   dérivé de ce champ, masquage à 0/erreur pendant le chargement, bascule propre
   sur erreur réseau. */

const attentionSummaryMock = vi.fn()
vi.mock('../api/notificationsApi', () => ({
  default: { attentionSummary: (...args) => attentionSummaryMock(...args) },
}))

import { useApprobationsCount } from './useApprobationsCount'

describe('useApprobationsCount (VX86/VX207)', () => {
  beforeEach(() => {
    attentionSummaryMock.mockReset()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('démarre à 0 en chargement', () => {
    attentionSummaryMock.mockReturnValue(new Promise(() => {})) // jamais résolu
    const { result } = renderHook(() => useApprobationsCount())
    expect(result.current.loading).toBe(true)
    expect(result.current.total).toBe(0)
    expect(result.current.error).toBe(false)
  })

  it('expose le total = champ `approbations` du résumé attention', async () => {
    attentionSummaryMock.mockResolvedValue({ data: { approbations: 2 } })
    const { result } = renderHook(() => useApprobationsCount())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.total).toBe(2)
    expect(result.current.error).toBe(false)
  })

  it('reste à 0 (jamais un total inventé) quand le résumé est vide', async () => {
    attentionSummaryMock.mockResolvedValue({ data: { approbations: 0 } })
    const { result } = renderHook(() => useApprobationsCount())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.total).toBe(0)
  })

  it('bascule error=true sur échec réseau, sans casser le total à une valeur inventée', async () => {
    attentionSummaryMock.mockRejectedValue(new Error('network'))
    const { result } = renderHook(() => useApprobationsCount())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe(true)
    expect(result.current.total).toBe(0)
  })
})
