import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, within, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

/* PV23 — entrées 3D de la liste des devis. Un devis encore OUVERT (brouillon /
   envoyé) se CONÇOIT (`/ventes/devis/:id/design`, l'écran PV20/PV21 qui
   resynchronise ses lignes) ; un devis FIGÉ ne se conçoit plus — il se
   CONSULTE (`/ventes/devis/:id/3d`), et seulement s'il porte réellement un plan
   (`roof_layout`, déjà exposé par le serializer : aucun champ backend ajouté). */

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

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import DevisList from './DevisList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const devisBase = {
  id: 1, reference: 'DEV-2026-07-0001', client_nom: 'ACME',
  date_creation: '2026-07-01', total_ttc: 12000, nb_options: 1, version: 1,
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

describe('PV23 — entrées 3D par statut (liste des devis)', () => {
  it('brouillon : « Concevoir en 3D » ouvre l\'écran de conception du devis', async () => {
    renderList([{ ...devisBase, statut: 'brouillon' }])
    const user = await ouvrirMenu('DEV-2026-07-0001')
    const entree = await screen.findByRole('menuitem',
      { name: /Concevoir la toiture 3D de DEV-2026-07-0001/ })
    expect(screen.queryByRole('menuitem', { name: /Voir le design 3D/ })).toBeNull()
    await user.click(entree)
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/1/design')
  })

  it('envoyé : la conception reste offerte (le calepinage peut encore bouger)', async () => {
    renderList([{ ...devisBase, statut: 'envoye' }])
    await ouvrirMenu('DEV-2026-07-0001')
    expect(await screen.findByRole('menuitem',
      { name: /Concevoir la toiture 3D de DEV-2026-07-0001/ })).toBeInTheDocument()
  })

  it('figé AVEC plan : plus de conception, seulement la consultation 3D', async () => {
    renderList([{
      ...devisBase, statut: 'accepte',
      roof_layout: { version: 2, zones: [] },
    }])
    const user = await ouvrirMenu('DEV-2026-07-0001')
    expect(screen.queryByRole('menuitem', { name: /Concevoir la toiture 3D/ })).toBeNull()
    const entree = await screen.findByRole('menuitem',
      { name: /Voir le design 3D de DEV-2026-07-0001/ })
    await user.click(entree)
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/1/3d')
  })

  it('figé SANS plan : aucune entrée 3D — on ne propose pas une page vide', async () => {
    renderList([{ ...devisBase, statut: 'refuse', roof_layout: null }])
    await ouvrirMenu('DEV-2026-07-0001')
    expect(await screen.findByText("Plus d'actions")).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /Concevoir la toiture 3D/ })).toBeNull()
    expect(screen.queryByRole('menuitem', { name: /Voir le design 3D/ })).toBeNull()
  })

  it('expiré à la volée (is_expired) : traité comme figé, pas comme envoyé', async () => {
    renderList([{
      ...devisBase, statut: 'envoye', is_expired: true,
      roof_layout: { version: 2, zones: [] },
    }])
    await ouvrirMenu('DEV-2026-07-0001')
    expect(screen.queryByRole('menuitem', { name: /Concevoir la toiture 3D/ })).toBeNull()
    expect(await screen.findByRole('menuitem',
      { name: /Voir le design 3D de DEV-2026-07-0001/ })).toBeInTheDocument()
  })
})
