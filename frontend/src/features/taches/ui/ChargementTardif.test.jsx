import { Suspense, lazy } from 'react'
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Frontiere from '../ecrans/Frontiere'
import ChargementTardif from './ChargementTardif'

vi.mock('../ecrans/precharger', () => ({ prechargerEcrans: vi.fn(), CHARGEURS: {} }))

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

describe("R4-VERIF-4 — du repli de la frontière au squelette de l'écran, sans trou", () => {
  it('un écran monté APRÈS le repli de sa frontière montre son squelette tout de suite (pas de 300 ms de vide)', async () => {
    let livrer
    const Ecran = () => (<main><ChargementTardif actif /></main>)
    const Page = lazy(() => new Promise((r) => { livrer = () => r({ default: Ecran }) }))
    render(<Frontiere ecran="projets" titre="Projets"><Page /></Frontiere>)
    // le repli de la frontière : un squelette
    expect(screen.getAllByRole('status', { name: 'Chargement' })).toHaveLength(1)
    await act(async () => { livrer() })
    // l'écran est monté, ses données ne sont pas là : le squelette de l'écran a pris la suite à l'instant même
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getAllByRole('status', { name: 'Chargement' })).toHaveLength(1)
    expect(screen.getByRole('status', { name: 'Chargement' }).closest('main')).not.toBeNull()
  })

  it('un écran déjà chargé (aucun repli) garde le délai de 300 ms : une réponse rapide ne fait rien clignoter', () => {
    render(<Suspense fallback={null}><Frontiere ecran="projets" titre="Projets"><main><ChargementTardif actif /></main></Frontiere></Suspense>)
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
    act(() => { vi.advanceTimersByTime(300) })
    expect(screen.getByRole('status', { name: 'Chargement' })).toBeInTheDocument()
  })

  it('après la première réponse, un nouveau chargement du même écran reprend le délai (jamais de clignotement sur un rafraîchissement)', async () => {
    let livrer
    const Ecran = ({ actif }) => (<main><ChargementTardif actif={actif} /></main>)
    const Page = lazy(() => new Promise((r) => { livrer = () => r({ default: Ecran }) }))
    const { rerender } = render(<Frontiere ecran="projets" titre="Projets"><Page actif /></Frontiere>)
    await act(async () => { livrer() })
    rerender(<Frontiere ecran="projets" titre="Projets"><Page actif={false} /></Frontiere>)
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
    rerender(<Frontiere ecran="projets" titre="Projets"><Page actif /></Frontiere>)
    expect(screen.queryByRole('status', { name: 'Chargement' })).toBeNull()
  })
})

