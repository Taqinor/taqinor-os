import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR133 — décision fondateur : saisie MANUELLE pour sinistres/infractions/
   trajets chantier (événements métier, aucun flux externe) ; télématique laissée
   MACHINE-FED (documentée, sans formulaire). On vérifie (1) qu'un sinistre se
   crée manuellement depuis l'onglet Sinistres et (2) que la décision télématique
   est documentée dans l'UI. Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { empty, sinistresCreate } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  sinistresCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    pleins: { list: empty, ocr: vi.fn() },
    cartes: { list: empty, anomalies: () => Promise.resolve({ data: { anomalies: [] } }), create: vi.fn(), update: vi.fn() },
    conducteurs: { list: () => Promise.resolve({ data: [{ id: 2, nom: 'Karim' }] }) },
    actifs: { list: () => Promise.resolve({ data: [{ id: 10, label: 'Camion 12345-A-6' }] }) },
    sinistres: { list: empty, create: (...a) => sinistresCreate(...a) },
    infractions: { list: empty, create: vi.fn() },
    vehicules: { list: empty },
    relevesTelematiques: { list: empty },
    trajetsTelematiques: { list: empty },
    trajetsChantier: { list: empty, create: vi.fn() },
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

describe('CarburantScreen — WIR133 saisie manuelle', () => {
  it('déclare manuellement un sinistre depuis l’onglet Sinistres', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)

    await user.click(screen.getByRole('tab', { name: 'Sinistres' }))
    await user.click(await screen.findByRole('button', { name: 'Déclarer un sinistre' }))

    await waitFor(() => expect(screen.getByLabelText('Actif')).toBeTruthy())
    await user.selectOptions(screen.getByLabelText('Actif'), '10')
    fireEvent.change(screen.getByLabelText('Date du sinistre'), { target: { value: '2026-07-01' } })
    fireEvent.change(screen.getByLabelText('Montant estimé (MAD)'), { target: { value: '5000' } })

    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(sinistresCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        actif_flotte: 10, date_sinistre: '2026-07-01',
        type_sinistre: 'accident_materiel', montant_estime: 5000,
      }),
    ))
  })

  it('documente la décision machine-fed sur l’onglet Télématique', async () => {
    const user = userEvent.setup()
    withProviders(<CarburantScreen />)

    await user.click(screen.getByRole('tab', { name: 'Télématique' }))
    await waitFor(() => expect(screen.getByText(/intégration télématique/i)).toBeTruthy())
  })
})
