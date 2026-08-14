import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, within, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* PV76 — entrée « Étude bancable » de la liste des devis.

   Test de MONTAGE (atteignabilité) : le menu « Plus d'actions » d'une ligne
   ouvre le panneau, qui monte `<EtudeBancable devis={d}>` — lequel lit
   `d.etude_params.simulation` (couvert en détail, PACT10 inclus, par
   `features/ventes/EtudeBancable.test.jsx`). Ici on vérifie seulement le
   CÂBLAGE : le bon devis passé en prop, le bon panneau affiché. */

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }) }
})
vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listSavedViews: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    createSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    updateSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    deleteSavedView: vi.fn(() => Promise.resolve({})),
  },
}))
vi.mock('../../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: { ...actual.default, getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })) },
  }
})

import DevisList from './DevisList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const SIMULATION = exempleContrat('ventes', 'simulation').simulation

const devisSansEtude = {
  id: 8, reference: 'DEV-2026-08-0008', client_nom: 'ACME', statut: 'brouillon',
  date_creation: '2026-08-01', total_ttc: 45000, nb_options: 1, version: 1,
  etude_params: {},
}
const devisAvecEtude = {
  ...devisSansEtude, id: 9, reference: 'DEV-2026-08-0009',
  etude_params: { simulation: SIMULATION },
}

function renderList(devis) {
  const store = configureStore({
    reducer: {
      ventes: (s = { devis, loading: false, error: null }) => s,
      auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/devis']}>
        <ThemeProvider>
          <DevisList />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

async function ouvrirMenu(reference) {
  const user = userEvent.setup()
  const row = screen.getByText(reference).closest('tr')
  await user.click(within(row).getByRole('button', { name: /Plus d'actions/ }))
  return user
}

describe('PV76 — « Étude bancable » (liste des devis)', () => {
  it('sans simulation : le panneau invite à lancer, jamais de carte de chiffres', async () => {
    renderList([devisSansEtude])
    const user = await ouvrirMenu(devisSansEtude.reference)
    const entree = await screen.findByRole('menuitem', { name: 'Étude bancable' })
    await user.click(entree)

    expect(await screen.findByText(`Étude bancable — ${devisSansEtude.reference}`))
      .toBeInTheDocument()
    expect(screen.getByText('Aucune étude bancable pour ce devis.')).toBeInTheDocument()
    expect(screen.queryByText(`${SIMULATION.projection_25y.payback_year} ans`)).toBeNull()
  })

  it('avec simulation : le panneau rend la carte lecture seule DU BON devis', async () => {
    renderList([devisSansEtude, devisAvecEtude])
    const user = await ouvrirMenu(devisAvecEtude.reference)
    const entree = await screen.findByRole('menuitem', { name: 'Étude bancable' })
    await user.click(entree)

    expect(await screen.findByText(`Étude bancable — ${devisAvecEtude.reference}`))
      .toBeInTheDocument()
    expect(screen.getByText(`${SIMULATION.projection_25y.payback_year} ans`))
      .toBeInTheDocument()

    // Le menu bascule vers « Masquer » une fois le panneau ouvert.
    await user.click(within(screen.getByText(devisAvecEtude.reference).closest('tr'))
      .getByRole('button', { name: /Plus d'actions/ }))
    expect(await screen.findByRole('menuitem', { name: "Masquer l'étude bancable" }))
      .toBeInTheDocument()
  })
})
