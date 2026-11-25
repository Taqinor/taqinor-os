import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../pleinEcran', () => ({
  basculerPleinEcran: vi.fn((element, doc, actuel) => Promise.resolve({ enPleinEcran: !actuel, repliCss: true })),
  estEnPleinEcranSur: () => false,
}))

const { useAtelierVues } = await import('./useAtelierVues')
const { ZOOM_MAX_CADRAGE_ATELIER } = await import('./useAtelierBoot')

// T4-X5-017 — la carte passait en plein écran sans que le toit soit recadré : il restait à sa place d'avant.
describe('useAtelierVues — plein écran de la carte', () => {
  it('T4-X5-017 — entrer en plein écran recadre le toit sur tout l’écran ; en sortir ne recadre pas', async () => {
    const cadrerToit = vi.fn(() => true)
    const builderApi = { current: { cadrerToit } }
    const { result } = renderHook(() => useAtelierVues({ builderApi, calepinageId: 1, devisId: null }))
    result.current.mapWrapRef.current = document.createElement('div')
    await act(async () => { result.current.basculerPleinEcran3d() })
    await waitFor(() => expect(result.current.pleinEcran3d).toBe(true))
    await waitFor(() => expect(cadrerToit).toHaveBeenCalledWith({ zoomMax: ZOOM_MAX_CADRAGE_ATELIER }))
    await act(async () => { result.current.basculerPleinEcran3d() })
    await waitFor(() => expect(result.current.pleinEcran3d).toBe(false))
    expect(cadrerToit).toHaveBeenCalledTimes(1)
  })
})
