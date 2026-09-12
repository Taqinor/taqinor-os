import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

/* CHT21(a) — `handleChantier` naviguait vers la liste nue `/chantiers`,
   forçant à re-sélectionner le chantier qu'on venait pourtant de désigner
   (ou de créer). Fichier de test dédié et minimal (patron
   DevisListCreerProjet.test.jsx), pour ne pas alourdir DevisList.test.jsx. */

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }) }
})

vi.mock('../../api/installationsApi', () => ({
  default: {
    createFromDevis: vi.fn(() => Promise.resolve({ data: { id: 99, reference: 'CH-0099' } })),
  },
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import DevisList from './DevisList'
import installationsApi from '../../api/installationsApi'
// ARC49 — le tableau DevisList passe par le moteur `ui/datatable` (useDensity),
// qui EXIGE un <ThemeProvider> (présent en prod via <Layout>).
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

function makeStore(devis) {
  return configureStore({
    reducer: {
      ventes: (state = { devis, loading: false, error: null }) => state,
      auth: (state = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => state,
    },
  })
}

function renderList(devis) {
  const store = makeStore(devis)
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

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DevisList — CHT21(a) deep-link chantier', () => {
  it('« Voir le chantier » (chantier déjà créé) navigue vers sa fiche, pas la liste nue', async () => {
    const devis = [{
      id: 7, reference: 'DEV-0007', statut: 'accepte', is_active: true,
      client_nom: 'Amine', date_creation: '2026-07-01', total_ttc: '100000',
      version: 1, chantier: { id: 55, reference: 'CH-0055', statut: 'signe' },
    }]
    const user = userEvent.setup()
    renderList(devis)
    await user.click(screen.getByRole('button', { name: /Plus d'actions/ }))
    await user.click(await screen.findByRole('menuitem', { name: /Voir le chantier CH-0055/ }))
    expect(navigateMock).toHaveBeenCalledWith('/chantiers?id=55')
  })

  it('« Créer le chantier » navigue vers la fiche du chantier nouvellement créé (pas la liste nue)', async () => {
    const devis = [{
      id: 7, reference: 'DEV-0007', statut: 'accepte', is_active: true,
      client_nom: 'Amine', date_creation: '2026-07-01', total_ttc: '100000',
      version: 1, chantier: null,
    }]
    const user = userEvent.setup()
    renderList(devis)
    await user.click(screen.getByRole('button', { name: /Plus d'actions/ }))
    await user.click(await screen.findByRole('menuitem', { name: /Créer le chantier/ }))
    await waitFor(() => expect(installationsApi.createFromDevis).toHaveBeenCalledWith(7))
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/chantiers?id=99'))
  })
})
