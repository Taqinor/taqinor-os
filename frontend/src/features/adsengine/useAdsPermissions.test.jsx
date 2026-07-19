import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

/* PUB10 — useAdsPermissions : réutilise `/auth/me/` (déjà consommé partout
   pour `state.auth.permissions`) sans dépendre de Redux. FAIL-CLOSED tant
   que le chargement n'est pas terminé et en cas d'échec réseau. */

const mocks = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('../../api/axios', () => ({
  default: { get: mocks.get },
}))

import { useAdsPermissions } from './useAdsPermissions'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useAdsPermissions (PUB10)', () => {
  it('fail-closed pendant le chargement : has() renvoie false', () => {
    mocks.get.mockReturnValue(new Promise(() => {})) // ne résout jamais dans ce test
    const { result } = renderHook(() => useAdsPermissions())
    expect(result.current.loading).toBe(true)
    expect(result.current.has('adsengine_approve')).toBe(false)
  })

  it('has() reflète les permissions renvoyées par /auth/me/', async () => {
    mocks.get.mockResolvedValue({ data: { permissions: ['adsengine_view', 'adsengine_manage'] } })
    const { result } = renderHook(() => useAdsPermissions())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.has('adsengine_manage')).toBe(true)
    expect(result.current.has('adsengine_approve')).toBe(false)
  })

  it('fail-closed sur un échec réseau (jamais de permission par défaut)', async () => {
    mocks.get.mockRejectedValue(new Error('network'))
    const { result } = renderHook(() => useAdsPermissions())
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.has('adsengine_approve')).toBe(false)
  })

  it('appelle bien /auth/me/ (endpoint léger déjà existant, aucun nouveau backend)', async () => {
    mocks.get.mockResolvedValue({ data: { permissions: [] } })
    renderHook(() => useAdsPermissions())
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('/auth/me/'))
  })
})
