import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import ReglagesRh from './ReglagesRh.jsx'

/* PACT94 — Réglages RH. Désactiver le rayon GPS (geofence) doit être posé à
   `null` côté serveur via PATCH `mon-reglage/` — effectif immédiatement sur le
   prochain pointage, sans redéploiement. */

vi.mock('../../api/rhApi', () => ({
  default: {
    getMonReglageRh: vi.fn(() => Promise.resolve({
      data: { id: 1, geofence_metres: 150, retention_candidatures_mois: 24, date_modification: '2026-08-01T10:00:00Z' },
    })),
    updateMonReglageRh: vi.fn(),
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ReglagesRh />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ReglagesRh (PACT94)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('charge le réglage existant (géofence active à 150 m)', async () => {
    renderScreen()
    expect((await screen.findAllByText('Réglages RH')).length).toBeGreaterThan(0)
    expect(await screen.findByLabelText('Rayon (mètres)')).toHaveValue(150)
  })

  it('désactive le rayon GPS via rhApi.updateMonReglageRh(geofence_metres: null)', async () => {
    rhApi.updateMonReglageRh.mockResolvedValueOnce({
      data: { id: 1, geofence_metres: null, retention_candidatures_mois: 24 },
    })
    renderScreen()
    await screen.findByLabelText('Rayon (mètres)')

    fireEvent.click(screen.getByRole('checkbox', { name: 'Contrôler le rayon GPS au pointage chantier' }))
    fireEvent.click(screen.getAllByRole('button', { name: 'Enregistrer' })[0])

    await waitFor(() => expect(rhApi.updateMonReglageRh).toHaveBeenCalledWith(
      expect.objectContaining({ geofence_metres: null }),
    ))
  })
})
