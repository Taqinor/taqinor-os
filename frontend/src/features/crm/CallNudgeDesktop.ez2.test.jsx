import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCallEndedNudge } from './CallLogPopover'

/* EZ2 — Le nudge « noter l'appel » marche AUSSI au bureau.
   ---------------------------------------------------------------------------
   État vérifié : le nudge ne dépendait que de `visibilitychange`. Exact sur
   téléphone (l'OS bascule sur l'app Téléphone puis revient) ; sur POSTE FIXE
   un tap `tel:` ne masque rien — l'événement ne part jamais, le nudge
   n'apparaît JAMAIS, et noter l'appel repasse par la fiche (7 clics).

   Trois déclencheurs, LE PREMIER GAGNE. Ces tests couvrent les DEUX chemins
   demandés (temporisation + retour de focus) et prouvent qu'ils ne se
   déclenchent jamais deux fois. */

const visible = (etat) => {
  Object.defineProperty(document, 'visibilityState', { value: etat, configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
}

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

describe('useCallEndedNudge (EZ2)', () => {
  it('ne propose RIEN tant qu’aucun appel n’a été armé', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 100 }))
    act(() => { vi.advanceTimersByTime(10_000) })
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(result.current.nudgeVisible).toBe(false)
  })

  it('BUREAU — la temporisation déclenche le nudge sans aucun changement d’onglet', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 45_000 }))
    act(() => { result.current.armCallNudge() })
    expect(result.current.nudgeVisible).toBe(false)
    act(() => { vi.advanceTimersByTime(45_000) })
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('BUREAU — le retour de FOCUS fenêtre déclenche le nudge (softphone)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 45_000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('MOBILE — le retour d’onglet reste le déclencheur d’origine (inchangé)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 45_000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { visible('visible') })
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('LE PREMIER GAGNE — un focus précoce désarme la temporisation (jamais deux nudges)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 45_000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(result.current.nudgeVisible).toBe(true)

    // Le nudge est écarté ; la temporisation d'origine ne doit PAS le rouvrir.
    act(() => { result.current.dismissNudge() })
    expect(result.current.nudgeVisible).toBe(false)
    act(() => { vi.advanceTimersByTime(60_000) })
    expect(result.current.nudgeVisible).toBe(false)
  })

  it('écarter le nudge désarme tout (aucun réveil fantôme)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 1_000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { result.current.dismissNudge() })
    act(() => { vi.advanceTimersByTime(5_000) })
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(result.current.nudgeVisible).toBe(false)
  })

  it('ré-armer repart d’un délai neuf (un 2e appel ne récupère pas le 1er timer)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 10_000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { vi.advanceTimersByTime(9_000) })
    act(() => { result.current.armCallNudge() })   // 2e appel
    act(() => { vi.advanceTimersByTime(9_000) })   // 18 s depuis le 1er
    expect(result.current.nudgeVisible).toBe(false)
    act(() => { vi.advanceTimersByTime(1_000) })   // 10 s depuis le 2e
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('un onglet resté en fond des heures ne surprend pas au retour (fenêtre 10 min)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 60 * 60 * 1000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { vi.advanceTimersByTime(20 * 60 * 1000) })
    act(() => { visible('visible') })
    expect(result.current.nudgeVisible).toBe(false)
  })

  it('le délai est INJECTABLE (la gate e2e peut l’avancer)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 50 }))
    act(() => { result.current.armCallNudge() })
    act(() => { vi.advanceTimersByTime(50) })
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('le démontage ne laisse aucun timer réveiller un composant mort', () => {
    const { result, unmount } = renderHook(() => useCallEndedNudge({ delayMs: 1_000 }))
    act(() => { result.current.armCallNudge() })
    unmount()
    // Aucune erreur « update on unmounted component » ne doit survenir.
    expect(() => { vi.advanceTimersByTime(5_000) }).not.toThrow()
  })
})
