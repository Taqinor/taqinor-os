import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR132 / XFLT14 — écran Garanties flotte : liste + création. Le badge de
   statut reflète le champ serveur `active` (couverture calculée). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const garantiesCreate = vi.fn(() => Promise.resolve({ data: { id: 1 } }))
vi.mock('../../api/flotteApi', () => ({
  default: {
    garanties: {
      list: () => Promise.resolve({
        data: [{
          id: 3, actif_flotte: 1, actif_label: '12345-A-6', composant: 'vehicule',
          duree_mois: 24, duree_km: 100000, date_debut: '2026-01-01',
          date_fin: '2028-01-01', active: true, fournisseur: 'Renault',
        }],
      }),
      create: (...a) => garantiesCreate(...a),
    },
  },
}))

import GarantiesFlotteTab from './GarantiesFlotteTab'

beforeEach(() => { vi.clearAllMocks() })

function renderTab() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <GarantiesFlotteTab actifs={[{ id: 1, label: '12345-A-6' }]} />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('WIR132 — Garanties flotte', () => {
  it('affiche une garantie existante avec badge « Sous garantie »', async () => {
    renderTab()
    expect((await screen.findAllByText('12345-A-6')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Sous garantie')).length).toBeGreaterThan(0)
  })

  it('crée une garantie via le formulaire', async () => {
    const user = userEvent.setup()
    renderTab()
    await user.click(await screen.findByRole('button', { name: 'Nouvelle garantie' }))
    await user.selectOptions(screen.getByLabelText('Actif (véhicule ou engin)'), '1')
    const debut = screen.getByLabelText('Date de début')
    await user.clear(debut)
    await user.type(debut, '2026-03-01')
    await user.type(screen.getByLabelText('Durée (mois)'), '12')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(garantiesCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        actif_flotte: 1, date_debut: '2026-03-01', duree_mois: 12, composant: 'vehicule',
      }),
    ))
  })
})
