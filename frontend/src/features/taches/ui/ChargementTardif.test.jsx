import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ChargementTardif from './ChargementTardif'

/* R2-089 — l'état « chargement » des écrans de Tâches : des lignes de tâches « os » (maquette etat-chargement.html)
   dès 300 ms, jamais avant (pas de clignotement sur une réponse rapide), et rien dès que l'écran a de quoi s'afficher.
   Nouveau fichier : aucun test n'existait pour ce composant. */

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

describe('ChargementTardif', () => {
  it('rien avant 300 ms, puis le squelette en lignes de tâches, annoncé « Chargement »', () => {
    const { container } = render(<ChargementTardif />)
    act(() => { vi.advanceTimersByTime(299) })
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
    act(() => { vi.advanceTimersByTime(1) })
    const squelette = screen.getByRole('status', { name: 'Chargement' })
    // la forme d'une liste de Tâches : des titres de section et des lignes (case + barres), aucun texte
    expect(squelette.querySelectorAll('.ligne .os.cercle').length).toBeGreaterThanOrEqual(5)
    expect(squelette.querySelectorAll('.os.titre-section').length).toBeGreaterThanOrEqual(2)
    expect(squelette.textContent).toBe('')
    expect(container.querySelectorAll('[aria-hidden="true"].ligne').length).toBe(squelette.querySelectorAll('.ligne').length)
  })

  it('R4-42 — le squelette de liste n\'est pas un `.squelette` (le bloc d\'une barre de 44 px de saisie.css : la liste y tenait écrasée)', () => {
    render(<ChargementTardif />)
    act(() => { vi.advanceTimersByTime(300) })
    const squelette = screen.getByRole('status', { name: 'Chargement' })
    expect(squelette).toHaveClass('squelette-liste')
    expect(squelette).not.toHaveClass('squelette')
  })

  it('inactif (l\'écran a sa réponse) : rien, même après le délai', () => {
    render(<ChargementTardif actif={false} />)
    act(() => { vi.advanceTimersByTime(2000) })
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
  })

  it('la réponse arrive avant 300 ms : le squelette n\'apparaît jamais', () => {
    const { rerender } = render(<ChargementTardif actif />)
    act(() => { vi.advanceTimersByTime(200) })
    rerender(<ChargementTardif actif={false} />)
    act(() => { vi.advanceTimersByTime(1000) })
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
  })
})
