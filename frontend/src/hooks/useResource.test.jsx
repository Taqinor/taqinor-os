import { describe, it, expect, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import useResource from './useResource'

/* ARC45 — useResource : fetch/état mutualisé (data/loading/error/refetch).
   On vérifie le cycle complet : chargement au montage, succès, erreur,
   refetch manuel, réactivité aux params, transformation `select`, garde de
   course (réponse périmée ignorée) et absence de mise à jour après démontage. */
describe('useResource (ARC45)', () => {
  it('charge au montage : loading vrai puis data au succès', async () => {
    const fetcher = vi.fn(() => Promise.resolve({ ok: 1 }))
    const { result } = renderHook(() => useResource(fetcher))

    expect(result.current.loading).toBe(true)
    expect(result.current.error).toBe(null)

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toEqual({ ok: 1 })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('passe le fetcher-résultat par `select` quand fourni', async () => {
    const fetcher = vi.fn(() => Promise.resolve({ data: [1, 2, 3] }))
    const { result } = renderHook(() =>
      useResource(fetcher, undefined, { select: (r) => r.data }))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toEqual([1, 2, 3])
  })

  it('expose un message d’erreur FR par défaut et garde data à l’état initial', async () => {
    const fetcher = vi.fn(() => Promise.reject(new Error('boom')))
    const { result } = renderHook(() =>
      useResource(fetcher, undefined, { initialData: [] }))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('Chargement impossible.')
    expect(result.current.data).toEqual([])
  })

  it('accepte un message d’erreur personnalisé (string ou fonction)', async () => {
    const fetcher = vi.fn(() => Promise.reject(new Error('x')))
    const { result } = renderHook(() =>
      useResource(fetcher, undefined, { errorMessage: 'Indispo.' }))
    await waitFor(() => expect(result.current.error).toBe('Indispo.'))

    const fetcher2 = vi.fn(() => Promise.reject(new Error('502')))
    const { result: r2 } = renderHook(() =>
      useResource(fetcher2, undefined, { errorMessage: (e) => `Erreur ${e.message}` }))
    await waitFor(() => expect(r2.current.error).toBe('Erreur 502'))
  })

  it('refetch() relance le fetcher et réinitialise l’erreur', async () => {
    let calls = 0
    const fetcher = vi.fn(() => {
      calls += 1
      return calls === 1 ? Promise.reject(new Error('1')) : Promise.resolve('ok')
    })
    const { result } = renderHook(() => useResource(fetcher))

    await waitFor(() => expect(result.current.error).toBe('Chargement impossible.'))

    await act(async () => { await result.current.refetch() })
    expect(result.current.error).toBe(null)
    expect(result.current.data).toBe('ok')
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('PARAMS RÉACTIFS : un changement de params relance le fetch', async () => {
    const fetcher = vi.fn((p) => Promise.resolve(p?.q ?? null))
    const { result, rerender } = renderHook(
      ({ p }) => useResource(fetcher, p),
      { initialProps: { p: { q: 'a' } } },
    )

    await waitFor(() => expect(result.current.data).toBe('a'))
    expect(fetcher).toHaveBeenCalledTimes(1)

    rerender({ p: { q: 'b' } })
    await waitFor(() => expect(result.current.data).toBe('b'))
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('ne relance PAS si la valeur des params est identique (clé stable)', async () => {
    const fetcher = vi.fn(() => Promise.resolve(1))
    const { result, rerender } = renderHook(
      ({ p }) => useResource(fetcher, p),
      { initialProps: { p: { q: 'a' } } },
    )
    await waitFor(() => expect(result.current.loading).toBe(false))
    // Nouvel objet, même contenu → même clé JSON → pas de refetch.
    rerender({ p: { q: 'a' } })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('GARDE DE COURSE : seule la dernière réponse gagne', async () => {
    const resolvers = []
    const fetcher = vi.fn(() => new Promise((res) => { resolvers.push(res) }))
    const { result, rerender } = renderHook(
      ({ p }) => useResource(fetcher, p),
      { initialProps: { p: { q: 'a' } } },
    )
    // Deux chargements en vol (params 'a' puis 'b').
    rerender({ p: { q: 'b' } })
    await waitFor(() => expect(resolvers.length).toBe(2))

    // La réponse du 2e (le plus récent) arrive d’abord…
    await act(async () => { resolvers[1]('B') })
    expect(result.current.data).toBe('B')
    // …puis la réponse périmée du 1er : elle doit être IGNORÉE.
    await act(async () => { resolvers[0]('A') })
    expect(result.current.data).toBe('B')
  })

  it('enabled:false ne charge pas ; loading reste faux', async () => {
    const fetcher = vi.fn(() => Promise.resolve(1))
    const { result } = renderHook(() =>
      useResource(fetcher, undefined, { enabled: false, initialData: 'x' }))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(fetcher).not.toHaveBeenCalled()
    expect(result.current.data).toBe('x')
  })

  it('ne met pas à jour l’état après démontage (abort via drapeau mounted)', async () => {
    let resolveFetch
    const fetcher = vi.fn(() => new Promise((res) => { resolveFetch = res }))
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { unmount } = renderHook(() => useResource(fetcher))

    // Attendre que le fetch soit réellement lancé (appel différé en microtâche).
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1))
    unmount()
    // Résoudre APRÈS le démontage : aucune erreur React « set state on unmounted ».
    await act(async () => { resolveFetch('tardif') })
    expect(spy).not.toHaveBeenCalled()
    spy.mockRestore()
  })
})
