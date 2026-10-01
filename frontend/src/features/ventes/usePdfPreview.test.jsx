import { describe, it, expect, afterEach } from 'vitest'
import { renderHook, act, waitFor, cleanup } from '@testing-library/react'
import { usePdfPreview } from './usePdfPreview'

// QJR653 — deux chargements successifs : le premier est ABANDONNÉ (signal
// avorté) et seul le second blob est affiché.
afterEach(cleanup)

function differe() {
  let resolve
  let reject
  const promesse = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promesse, resolve, reject }
}

describe('usePdfPreview', () => {
  it('abandonne le chargement précédent et n\'affiche que le second blob', async () => {
    const appels = []
    const fetchBlob = (signal) => {
      const d = differe()
      appels.push({ signal, ...d })
      return d.promesse
    }
    const { result } = renderHook(() => usePdfPreview(fetchBlob))
    await waitFor(() => expect(appels).toHaveLength(1))

    act(() => result.current.reload())
    await waitFor(() => expect(appels).toHaveLength(2))
    expect(appels[0].signal.aborted).toBe(true)
    expect(appels[1].signal.aborted).toBe(false)

    const second = new Blob(['2'])
    const premier = new Blob(['1'])
    await act(async () => { appels[1].resolve(second) })
    await act(async () => { appels[0].resolve(premier) })
    expect(result.current.blob).toBe(second)
    expect(result.current.loading).toBe(false)
  })

  it('classe un échec serveur (4xx/5xx) et un échec réseau', async () => {
    const erreurServeur = Object.assign(new Error('boom'), { response: { status: 500 } })
    const { result, rerender } = renderHook(
      ({ f }) => usePdfPreview(f),
      { initialProps: { f: () => Promise.reject(erreurServeur) } },
    )
    await waitFor(() => expect(result.current.errorKind).toBe('server'))
    rerender({ f: () => Promise.reject(new Error('réseau')) })
    await waitFor(() => expect(result.current.errorKind).toBe('network'))
  })

  it('désactivé : aucune requête et état purgé', async () => {
    let n = 0
    const f = () => { n += 1; return Promise.resolve(new Blob(['x'])) }
    const { result } = renderHook(() => usePdfPreview(f, { enabled: false }))
    expect(n).toBe(0)
    expect(result.current.blob).toBeNull()
    expect(result.current.loading).toBe(false)
  })
})
