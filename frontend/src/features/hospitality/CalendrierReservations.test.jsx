import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTHOT21 — calendrier réservations avec création par glisser-déposer :
   un conflit doit apparaître visuellement AVANT la validation (bouton de
   création désactivé), et une plage libre doit créer la réservation avec
   les bonnes dates (chambre × plage sélectionnée). Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof Element.prototype.hasPointerCapture === 'undefined') {
    Element.prototype.hasPointerCapture = () => false
  }
  if (typeof Element.prototype.scrollIntoView === 'undefined') {
    Element.prototype.scrollIntoView = () => {}
  }
})

function isoOf(offsetDays) {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().slice(0, 10)
}

const { createReservation } = vi.hoisted(() => ({
  createReservation: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
}))

vi.mock('../../api/hospitalityApi', () => ({
  default: {
    listChambres: () => Promise.resolve({
      data: [
        { id: 1, numero: '101', nom: '' },
        { id: 2, numero: '102', nom: '' },
      ],
    }),
    listReservations: () => Promise.resolve({
      data: [
        {
          id: 10, chambre: 2, statut: 'confirmee',
          date_arrivee: isoOf(1), date_depart: isoOf(3),
        },
      ],
    }),
    createReservation: (...args) => createReservation(...args),
  },
}))

import CalendrierReservations from './CalendrierReservations'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('CalendrierReservations (NTHOT21)', () => {
  it('glisser sur une plage libre ouvre la confirmation et crée la réservation', async () => {
    withProviders(<CalendrierReservations />)
    await waitFor(() => expect(screen.getByTestId('cell-1-0')).toBeTruthy())

    fireEvent.mouseDown(screen.getByTestId('cell-1-0'))
    fireEvent.mouseEnter(screen.getByTestId('cell-1-2'))
    fireEvent.mouseUp(screen.getByTestId('cell-1-2'))

    await waitFor(() => expect(screen.getByText('Créer la réservation')).toBeTruthy())
    expect(screen.getByText('Créer la réservation').closest('button')).not.toBeDisabled()

    fireEvent.click(screen.getByText('Créer la réservation'))

    await waitFor(() => expect(createReservation).toHaveBeenCalledWith({
      chambre: 1,
      date_arrivee: isoOf(0),
      date_depart: isoOf(3),
    }))
  })

  it('un conflit sur une chambre déjà occupée désactive la création', async () => {
    withProviders(<CalendrierReservations />)
    await waitFor(() => expect(screen.getByTestId('cell-2-0')).toBeTruthy())

    // Chambre 2 est occupée aux indices 1 et 2 (isoOf(1)..isoOf(2)) —
    // sélectionner 0..2 traverse la réservation existante.
    fireEvent.mouseDown(screen.getByTestId('cell-2-0'))
    fireEvent.mouseEnter(screen.getByTestId('cell-2-2'))
    fireEvent.mouseUp(screen.getByTestId('cell-2-2'))

    await waitFor(() => expect(screen.getByText(/Conflit/)).toBeTruthy())
    expect(screen.getByText('Créer la réservation').closest('button')).toBeDisabled()
    expect(createReservation).not.toHaveBeenCalled()
  })
})
