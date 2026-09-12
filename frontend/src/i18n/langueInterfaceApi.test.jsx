import { describe, it, expect, vi, afterEach } from 'vitest'

/* NTI18N3 — `patchLangueInterface` doit appeler le bon endpoint avec le bon
   corps, et rester silencieux (jamais lever) en cas d'échec réseau/session
   — c'est un « bonus » de confort multi-poste, jamais bloquant pour la
   bascule de langue LOCALE déjà appliquée avant cet appel. */

const patchMock = vi.fn()
vi.mock('../api/axios', () => ({
  default: { patch: (...args) => patchMock(...args) },
}))

import { patchLangueInterface } from './langueInterfaceApi'

afterEach(() => { patchMock.mockReset() })

describe('NTI18N3 patchLangueInterface', () => {
  it('appelle PATCH /auth/me/langue/ avec la locale', async () => {
    patchMock.mockResolvedValue({ data: { langue_interface: 'ar' } })
    const ok = await patchLangueInterface('ar')
    expect(ok).toBe(true)
    expect(patchMock).toHaveBeenCalledWith(
      '/auth/me/langue/', { langue_interface: 'ar' },
      expect.objectContaining({ suppressErrorToast: true }),
    )
  })

  it('ne lève jamais en cas d’échec, renvoie false', async () => {
    patchMock.mockRejectedValue(new Error('réseau indisponible'))
    const ok = await patchLangueInterface('en')
    expect(ok).toBe(false)
  })
})
