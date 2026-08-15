// NTMOB18 — verrouillage d'écran local.
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import {
  isAppLockEnabled, disableAppLock, shouldLock, markHidden, clearHidden,
  setLockDelayMinutes, getLockDelayMinutes, DEFAULT_LOCK_DELAY_MIN,
  setPin, verifyPin, hasPin, LOCK_ENABLED_KEY,
} from './appLock'
import AppLockGate from './AppLockGate'

describe('NTMOB18 — logique du verrou', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('est désactivé par défaut et ne verrouille jamais', () => {
    expect(isAppLockEnabled()).toBe(false)
    markHidden(1_700_000_000_000)
    expect(shouldLock(1_700_000_600_000)).toBe(false)
  })

  it('verrouille seulement au-delà du délai de veille configuré', () => {
    localStorage.setItem(LOCK_ENABLED_KEY, '1')
    expect(getLockDelayMinutes()).toBe(DEFAULT_LOCK_DELAY_MIN)
    const t0 = 1_700_000_000_000
    markHidden(t0)
    // 2 minutes de veille : un aller-retour bref ne reverrouille pas.
    expect(shouldLock(t0 + 2 * 60_000)).toBe(false)
    // 5 minutes : le critère d'acceptation.
    expect(shouldLock(t0 + 5 * 60_000)).toBe(true)
    setLockDelayMinutes(15)
    expect(shouldLock(t0 + 5 * 60_000)).toBe(false)
    clearHidden()
    expect(shouldLock(Number.MAX_SAFE_INTEGER)).toBe(false)
  })

  it('stocke le code de secours haché, jamais en clair', async () => {
    await setPin('1234')
    expect(hasPin()).toBe(true)
    expect(localStorage.getItem('app.lock.pin')).not.toContain('1234')
    expect(await verifyPin('1234')).toBe(true)
    expect(await verifyPin('9999')).toBe(false)
  })

  it('efface tout l\'état local à la désactivation', async () => {
    localStorage.setItem(LOCK_ENABLED_KEY, '1')
    await setPin('1234')
    disableAppLock()
    expect(isAppLockEnabled()).toBe(false)
    expect(hasPin()).toBe(false)
  })
})

describe('NTMOB18 — écran de verrouillage', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('ne rend rien quand le verrou est désactivé', () => {
    const { container } = render(<AppLockGate />)
    expect(container).toBeEmptyDOMElement()
  })

  it('masque le contenu au retour de veille et se déverrouille au bon code', async () => {
    localStorage.setItem(LOCK_ENABLED_KEY, '1')
    await setPin('1234')
    // L'app a été mise en veille il y a plus de 5 minutes.
    markHidden(Date.now() - 6 * 60_000)
    render(<AppLockGate />)
    act(() => { document.dispatchEvent(new Event('visibilitychange')) })
    expect(screen.getByRole('dialog', { name: 'Application verrouillée' })).toBeTruthy()

    fireEvent.change(screen.getByLabelText(/Ou saisissez votre code/), { target: { value: '0000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Valider' }))
    await screen.findByRole('alert')

    fireEvent.change(screen.getByLabelText(/Ou saisissez votre code/), { target: { value: '1234' } })
    fireEvent.click(screen.getByRole('button', { name: 'Valider' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})
