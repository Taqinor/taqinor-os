import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT25 — codes défaut moteur (DTC) affichés sur les relevés télématiques,
   et XFLT23 — création d'un plein via le nouveau bouton. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { empty, anomalies } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  anomalies: vi.fn(() => Promise.resolve({
    data: {
      nb_pleins: 5,
      nb_anomalies: 1,
      anomalies: [{
        plein_id: 3, type: 'km_recul', gravite: 'haute',
        message: 'Kilométrage en recul détecté', date_plein: '2026-07-01',
      }],
    },
  })),
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    pleins: { list: empty, ocr: vi.fn() },
    cartes: { list: empty, anomalies: (...args) => anomalies(...args) },
    sinistres: { list: empty },
    infractions: { list: empty },
    vehicules: { list: () => Promise.resolve({ data: [{ id: 1, immatriculation: '12345-A-6' }] }) },
    relevesTelematiques: { list: () => Promise.resolve({
      data: [{ id: 1, actif_label: '12345-A-6', horodatage: '2026-07-01T08:00:00Z', codes_defaut: ['P0300', 'P0171'] }],
    }) },
    trajetsTelematiques: { list: empty },
    trajetsChantier: { list: empty },
  },
}))

import CarburantScreen from './CarburantScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('CarburantScreen — Télématique (XFLT25 DTC)', () => {
  it('affiche les codes défaut moteur sur les relevés télématiques', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)

    await user.click(screen.getByRole('tab', { name: 'Télématique' }))
    // DataTable rend la table desktop ET les cartes mobiles dans le DOM (le
    // point de rupture est géré en CSS) : deux correspondances attendues.
    await waitFor(() => expect(screen.getAllByText('P0300, P0171').length).toBeGreaterThan(0))
  })
})

describe('CarburantScreen — Cartes (WIR6 anomalies)', () => {
  it('affiche une anomalie détectée sur l’onglet Cartes', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)

    await user.click(screen.getByRole('tab', { name: 'Cartes' }))
    await waitFor(() => expect(anomalies).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByText('Kilométrage en recul détecté')).toBeInTheDocument())
  })
})

describe('CarburantScreen — Carburant (XFLT23 bouton nouveau plein)', () => {
  it('ouvre le formulaire de nouveau plein', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)

    await user.click(screen.getByRole('button', { name: 'Nouveau plein' }))
    expect(screen.getByRole('heading', { name: 'Nouveau plein' })).toBeInTheDocument()
  })
})
