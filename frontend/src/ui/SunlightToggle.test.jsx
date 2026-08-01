import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* EZ9 — mode « Plein soleil » : bascule instantanée sur les écrans terrain,
   persistée, et implémentée en ATTRIBUT sur <html> (patron [data-density]) —
   jamais un troisième thème. */

import { SunlightToggle } from './SunlightToggle'
import { getSunlightPref, setSunlightPref, applySunlight, SUNLIGHT_KEY } from '../pages/preferences/prefs'

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-sunlight')
})
afterEach(() => {
  cleanup()
  localStorage.clear()
  document.documentElement.removeAttribute('data-sunlight')
})

describe('EZ9 · préférence « Plein soleil »', () => {
  it('est éteinte par défaut (aucun attribut posé)', () => {
    expect(getSunlightPref()).toBe(false)
    expect(document.documentElement.hasAttribute('data-sunlight')).toBe(false)
  })

  it('l’activation pose data-sunlight="1" et persiste', () => {
    setSunlightPref(true)
    expect(document.documentElement.getAttribute('data-sunlight')).toBe('1')
    expect(localStorage.getItem(SUNLIGHT_KEY)).toBe('1')
    expect(getSunlightPref()).toBe(true)
  })

  it('la désactivation RETIRE l’attribut (aucun état résiduel)', () => {
    setSunlightPref(true)
    setSunlightPref(false)
    expect(document.documentElement.hasAttribute('data-sunlight')).toBe(false)
    expect(getSunlightPref()).toBe(false)
  })

  it('applySunlight ne touche pas le stockage (application seule)', () => {
    applySunlight(true)
    expect(document.documentElement.getAttribute('data-sunlight')).toBe('1')
    expect(localStorage.getItem(SUNLIGHT_KEY)).toBeNull()
  })
})

describe('EZ9 · bascule sur l’écran terrain', () => {
  it('bascule instantanément et annonce son état (aria-pressed)', async () => {
    const user = userEvent.setup()
    render(<SunlightToggle />)
    const btn = screen.getByTestId('sunlight-toggle')
    expect(btn).toHaveAttribute('aria-pressed', 'false')
    await user.click(btn)
    expect(btn).toHaveAttribute('aria-pressed', 'true')
    expect(document.documentElement.getAttribute('data-sunlight')).toBe('1')
    await user.click(btn)
    expect(btn).toHaveAttribute('aria-pressed', 'false')
    expect(document.documentElement.hasAttribute('data-sunlight')).toBe(false)
  })

  it('reprend l’état persisté au montage', () => {
    setSunlightPref(true)
    render(<SunlightToggle />)
    expect(screen.getByTestId('sunlight-toggle')).toHaveAttribute('aria-pressed', 'true')
  })
})
