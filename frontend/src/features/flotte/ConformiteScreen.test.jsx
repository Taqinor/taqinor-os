import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR236 — l'onglet « Contrats » (XFLT1, `contratsVehicule.expirants`)
   n'avait aucun écran : la bascule « Contrats expirants 30 j » bascule le
   fetcher list() → expirants({within: 30}). Réseau mocké. */

const empty = () => Promise.resolve({ data: [] })
const contratsList = vi.fn(() => Promise.resolve({
  data: [{ id: 1, vehicule_label: '12345-A-6', type_contrat_display: 'Leasing', fournisseur: 'ALD', date_fin: '2026-12-01', statut_calcule: 'actif' }],
}))
const contratsExpirants = vi.fn(() => Promise.resolve({
  data: [{ id: 2, vehicule_label: '98765-B-1', type_contrat_display: 'LLD', fournisseur: 'Arval', date_fin: '2026-09-01', statut_calcule: 'actif' }],
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    echeancesReglementaires: { list: empty },
    assurances: { list: empty },
    visitesTechniques: { list: empty },
    cartesGrises: { list: empty },
    baremesVignette: { list: empty },
    alertesEcheances: () => Promise.resolve({ data: [] }),
    contratsVehicule: {
      list: (...args) => contratsList(...args),
      expirants: (...args) => contratsExpirants(...args),
    },
  },
}))

import ConformiteScreen from './ConformiteScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ConformiteScreen — Contrats (WIR236)', () => {
  it('liste tous les contrats par défaut, puis bascule sur les contrats expirants sous 30 j', async () => {
    const user = userEvent.setup()
    withProviders(<ConformiteScreen />)
    await user.click(screen.getByRole('tab', { name: 'Contrats' }))

    await waitFor(() => expect(contratsList).toHaveBeenCalled())
    expect((await screen.findAllByText('ALD')).length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Contrats expirants 30 j' }))
    await waitFor(() => expect(contratsExpirants).toHaveBeenCalledWith({ within: 30 }))
    expect(await screen.findAllByText('Arval')).not.toHaveLength(0)
  })
})
