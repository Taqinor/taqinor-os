// @vitest-environment jsdom
/* CAD177 — le tirage retient le scroll natif par un écouteur `touchmove` NATIF
   non passif : React enregistre `touchmove` en PASSIF à la racine, où
   `preventDefault()` est sans effet (et journalise une erreur Chrome à chaque
   mouvement — constat du marcheur aléatoire QAH7). */
import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render } from '@testing-library/react'
import { usePullToRefresh } from './usePullToRefresh'

function Zone({ onRefresh }) {
  const { containerProps, pullDistance } = usePullToRefresh(onRefresh)
  return (
    <div data-testid="zone" {...containerProps}>
      <span data-testid="distance">{pullDistance}</span>
    </div>
  )
}

function toucher(type, y) {
  const e = new Event(type, { bubbles: true, cancelable: true })
  Object.defineProperty(e, 'touches', { value: [{ clientX: 0, clientY: y }] })
  return e
}

describe('usePullToRefresh — touchmove natif non passif (CAD177)', () => {
  it('pose touchmove en { passive: false } et plus en prop React', () => {
    const espion = vi.spyOn(HTMLElement.prototype, 'addEventListener')
    const { getByTestId } = render(<Zone onRefresh={() => {}} />)
    const zone = getByTestId('zone')
    const appel = espion.mock.calls.find(
      ([type], i) => type === 'touchmove' && espion.mock.contexts[i] === zone)
    espion.mockRestore()
    expect(appel).toBeTruthy()
    expect(appel[2]).toEqual({ passive: false })
  })

  it('un tirage vers le bas depuis le haut retient le scroll et suit le doigt', () => {
    const { getByTestId } = render(<Zone onRefresh={() => {}} />)
    const zone = getByTestId('zone')
    act(() => { zone.dispatchEvent(toucher('touchstart', 0)) })
    const mouvement = toucher('touchmove', 80)
    act(() => { zone.dispatchEvent(mouvement) })
    expect(mouvement.defaultPrevented).toBe(true)
    expect(Number(getByTestId('distance').textContent)).toBeGreaterThan(0)
  })

  it('un geste vers le haut ne retient rien (le scroll normal passe)', () => {
    const { getByTestId } = render(<Zone onRefresh={() => {}} />)
    const zone = getByTestId('zone')
    act(() => { zone.dispatchEvent(toucher('touchstart', 100)) })
    const mouvement = toucher('touchmove', 40)
    act(() => { zone.dispatchEvent(mouvement) })
    expect(mouvement.defaultPrevented).toBe(false)
    fireEvent.touchEnd(zone)
    expect(getByTestId('distance').textContent).toBe('0')
  })
})
