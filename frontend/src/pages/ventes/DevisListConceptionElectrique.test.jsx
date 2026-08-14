import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, within, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { reponseContrat } from '../../test/fixtures/contractSamples'

/* PV43 — entrée « Conception électrique » de la liste des devis.

   Test de MONTAGE (atteignabilité) : le menu « Plus d'actions » d'une ligne
   ouvre le panneau, qui monte `<ConceptionElectrique devisId={d.id}>` — lequel
   fait son propre appel réseau (couvert en détail, PACT10 inclus, par
   `features/ventes/ConceptionElectrique.test.jsx`). Ici on vérifie seulement
   le CÂBLAGE : le bon devis, la bonne API, le bon panneau. */

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
vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getConceptionElectrique: vi.fn(),
      getSchemaUnifilaireDevis: vi.fn(() => Promise.resolve({ data: { params: {}, svg: null } })),
    },
  }
})

import DevisList from './DevisList'
import ventesApi from '../../api/ventesApi'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const devisBase = {
  id: 3, reference: 'DEV-2026-08-0003', client_nom: 'ACME', statut: 'brouillon',
  date_creation: '2026-08-01', total_ttc: 45000, nb_options: 1, version: 1,
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

describe('PV43 — « Conception électrique » (liste des devis)', () => {
  it('le menu ouvre le panneau et monte <ConceptionElectrique> pour LE BON devis', async () => {
    ventesApi.getConceptionElectrique.mockResolvedValue(
      reponseContrat('ventes', 'conception_electrique'))
    renderList([devisBase])
    const user = await ouvrirMenu(devisBase.reference)

    const entree = await screen.findByRole('menuitem', { name: 'Conception électrique' })
    await user.click(entree)

    await waitFor(() => expect(ventesApi.getConceptionElectrique)
      .toHaveBeenCalledWith(devisBase.id))
    expect(await screen.findByText(`Conception électrique — ${devisBase.reference}`))
      .toBeInTheDocument()

    // Le menu bascule vers « Masquer » une fois le panneau ouvert.
    await user.click(within(screen.getByText(devisBase.reference).closest('tr'))
      .getByRole('button', { name: /Plus d'actions/ }))
    expect(await screen.findByRole('menuitem', { name: 'Masquer la conception électrique' }))
      .toBeInTheDocument()
  })

  it('deux devis distincts : chacun ouvre SON PROPRE panneau, sur SON id', async () => {
    ventesApi.getConceptionElectrique.mockResolvedValue(
      reponseContrat('ventes', 'conception_electrique'))
    const autre = { ...devisBase, id: 4, reference: 'DEV-2026-08-0004' }
    renderList([devisBase, autre])

    const user = await ouvrirMenu(autre.reference)
    const entree = await screen.findByRole('menuitem', { name: 'Conception électrique' })
    await user.click(entree)

    await waitFor(() => expect(ventesApi.getConceptionElectrique)
      .toHaveBeenCalledWith(autre.id))
    expect(ventesApi.getConceptionElectrique).not.toHaveBeenCalledWith(devisBase.id)
    expect(screen.queryByText(`Conception électrique — ${devisBase.reference}`)).toBeNull()
  })
})
