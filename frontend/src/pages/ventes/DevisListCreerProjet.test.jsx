import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

/* XPRJ21 — « Créer projet » sur un devis ACCEPTÉ : action utilisateur
   explicite (jamais automatique) qui crée le Projet (gestion_projet) depuis
   le devis puis navigue vers sa fiche. Fichier de test dédié et minimal pour
   ne pas alourdir DevisList.test.jsx (qui mocke déjà beaucoup de surface). */

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }) }
})

vi.mock('../../api/gestionProjetApi', () => ({
  default: {
    creerProjetDepuisDevis: vi.fn(() => Promise.resolve({ data: { id: 42, code: 'PRJ-0042' } })),
  },
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import DevisList from './DevisList'
import gestionProjetApi from '../../api/gestionProjetApi'
// ARC49 — le tableau DevisList passe par le moteur `ui/datatable` (useDensity),
// qui EXIGE un <ThemeProvider> (présent en prod via <Layout>). Wrapper de
// harnais uniquement — aucune assertion modifiée.
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

const devisAccepte = [{
  id: 7, reference: 'DEV-0007', statut: 'accepte', is_active: true,
  client_nom: 'Amine', date_creation: '2026-07-01', total_ttc: '100000',
  version: 1,
}]

describe('DevisList — XPRJ21 Créer projet depuis devis', () => {
  // VX20 — « Créer projet » vit désormais dans le menu « Plus d'actions »
  // (regroupement des actions secondaires, plus de bouton direct).
  it('affiche l\'action « Créer projet » dans le menu « Plus » uniquement sur un devis accepté', async () => {
    const user = userEvent.setup()
    renderList(devisAccepte)
    await user.click(screen.getByRole('button', { name: /Plus d'actions/ }))
    expect(await screen.findByRole('menuitem', { name: /Créer projet/ })).toBeInTheDocument()
  })

  it('appelle creerProjetDepuisDevis puis navigue vers la fiche projet créée', async () => {
    const user = userEvent.setup()
    renderList(devisAccepte)
    await user.click(screen.getByRole('button', { name: /Plus d'actions/ }))
    await user.click(await screen.findByRole('menuitem', { name: /Créer projet/ }))
    await waitFor(() => expect(gestionProjetApi.creerProjetDepuisDevis).toHaveBeenCalledWith(7))
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/projets/42'))
  })
})
