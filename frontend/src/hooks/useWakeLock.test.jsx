// NTMOB29 — Wake Lock pendant une session de capture active.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import useWakeLock, { isWakeLockSupported } from './useWakeLock'

function Sonde({ actif }) {
  useWakeLock(actif)
  return null
}

describe('NTMOB29 — useWakeLock', () => {
  let release

  beforeEach(() => {
    release = vi.fn()
    Object.defineProperty(navigator, 'wakeLock', {
      value: { request: vi.fn(async () => ({ release })) },
      configurable: true,
      writable: true,
    })
  })

  afterEach(() => {
    delete navigator.wakeLock
  })

  it('acquiert la sentinelle pendant la session et la relâche à la fermeture', async () => {
    const { rerender } = render(<Sonde actif />)
    await waitFor(() => expect(navigator.wakeLock.request).toHaveBeenCalledWith('screen'))
    rerender(<Sonde actif={false} />)
    await waitFor(() => expect(release).toHaveBeenCalled())
  })

  it('ne demande rien quand aucune session n\'est active', () => {
    render(<Sonde actif={false} />)
    expect(navigator.wakeLock.request).not.toHaveBeenCalled()
  })

  it('dégrade silencieusement si l\'API est absente', () => {
    delete navigator.wakeLock
    expect(isWakeLockSupported()).toBe(false)
    expect(() => render(<Sonde actif />)).not.toThrow()
  })

  it('dégrade silencieusement si la permission est refusée', async () => {
    navigator.wakeLock.request = vi.fn(async () => { throw new Error('refusé') })
    expect(() => render(<Sonde actif />)).not.toThrow()
    await waitFor(() => expect(navigator.wakeLock.request).toHaveBeenCalled())
  })
})
