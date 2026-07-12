import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, act } from '@testing-library/react'
import { FieldSavedPulse } from './FieldSavedPulse'

/* VX249(a) — micro-accusé au GRAIN DU CHAMP pour une sauvegarde silencieuse
   (édition inline DataTable, statut, note chatter) : jusqu'ici, aucune
   confirmation locale — soit rien, soit un toast générique déconnecté de LA
   cellule modifiée. Pulse vert bref (300-400 ms, --motion-pulse) sur la
   cellule elle-même. */

afterEach(() => { cleanup(); vi.useRealTimers() })

describe('FieldSavedPulse (VX249a)', () => {
  it('pulseKey initial (0/null/undefined) ne pulse JAMAIS au montage', () => {
    render(<FieldSavedPulse pulseKey={0}><span>valeur</span></FieldSavedPulse>)
    expect(screen.getByText('valeur').parentElement).not.toHaveClass('field-saved-pulse')
  })

  it('incrémenter pulseKey déclenche la classe field-saved-pulse', () => {
    const { rerender } = render(
      <FieldSavedPulse pulseKey={0}><span>valeur</span></FieldSavedPulse>,
    )
    rerender(<FieldSavedPulse pulseKey={1}><span>valeur</span></FieldSavedPulse>)
    expect(screen.getByText('valeur').parentElement).toHaveClass('field-saved-pulse')
  })

  it('le pulse retombe après le délai (jamais un état bloqué)', () => {
    vi.useFakeTimers()
    const { rerender } = render(
      <FieldSavedPulse pulseKey={0}><span>valeur</span></FieldSavedPulse>,
    )
    rerender(<FieldSavedPulse pulseKey={1}><span>valeur</span></FieldSavedPulse>)
    expect(screen.getByText('valeur').parentElement).toHaveClass('field-saved-pulse')
    act(() => { vi.advanceTimersByTime(600) })
    expect(screen.getByText('valeur').parentElement).not.toHaveClass('field-saved-pulse')
  })

  it('`as` et `className` restent composables (jamais un wrapper figé)', () => {
    render(
      <FieldSavedPulse pulseKey={1} as="td" className="ta-right">
        <span>42</span>
      </FieldSavedPulse>,
    )
    const cell = screen.getByText('42').parentElement
    expect(cell.tagName).toBe('TD')
    expect(cell).toHaveClass('ta-right')
    expect(cell).toHaveClass('field-saved-pulse')
  })
})
