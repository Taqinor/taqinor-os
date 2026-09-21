import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* AUDV06 / XACC17-XACC18 — l'écran « Devises & change ».

   Quatre services complets vivaient sans ViewSet ni écran : la table FX était
   inatteignable hors admin Django (tout document en devise retombait en
   silence sur un change 1:1) et l'écart de change n'entrait jamais au grand
   livre. La charge utile du poste ouvert vient de l'exemple COMMITTÉ
   (`apps/compta/contract_samples/devise_poste_ouvert.json`), celui-là même que
   `apps/compta/tests/test_audv06_devises_rest.py` affirme contre la vraie
   réponse de la vue — jamais un objet retapé ici. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  tauxList: vi.fn(),
  postesList: vi.fn(),
  constaterEcart: vi.fn(),
  reevaluationsList: vi.fn(),
  lancer: vi.fn(),
  vide: () => Promise.resolve({ data: [] }),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    tauxDevise: {
      list: mocks.tauxList, get: mocks.vide, create: mocks.vide,
      update: mocks.vide, remove: mocks.vide,
    },
    itemsOuvertsDevise: {
      list: mocks.postesList, get: mocks.vide, create: mocks.vide,
      update: mocks.vide, remove: mocks.vide,
      constaterEcart: mocks.constaterEcart,
    },
    reevaluationsCloture: {
      list: mocks.reevaluationsList, get: mocks.vide, lancer: mocks.lancer,
    },
  },
}))

import DevisesPage from './DevisesPage.jsx'

function mount({ route = '/' } = {}) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]}>
        <ThemeProvider><DevisesPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('DevisesPage — taux de change (XACC17)', () => {
  it('liste les taux saisis avec leur source', async () => {
    mocks.tauxList.mockResolvedValue({
      data: [{ id: 1, devise: 'EUR', date_taux: '2026-06-01',
        taux_vers_mad: '10.850000', source: 'manuel',
        source_display: 'Saisie manuelle' }],
    })
    mocks.postesList.mockResolvedValue({ data: [] })
    mocks.reevaluationsList.mockResolvedValue({ data: [] })

    mount()

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Devises & change/ }))
        .toBeInTheDocument()
    })
    expect((await screen.findAllByText('EUR')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Saisie manuelle')).length)
      .toBeGreaterThan(0)
  }, 30000)
})

describe('DevisesPage — écart de change réalisé (XACC18)', () => {
  it('constate l’écart d’un poste OUVERT et n’en propose aucun sur un poste soldé', async () => {
    const ouvert = exempleContrat('compta', 'devise_poste_ouvert', 'exemple_non_solde')
    const solde = exempleContrat('compta', 'devise_poste_ouvert')
    mocks.tauxList.mockResolvedValue({ data: [] })
    mocks.reevaluationsList.mockResolvedValue({ data: [] })
    mocks.postesList.mockResolvedValue({ data: [ouvert, solde] })
    mocks.constaterEcart.mockResolvedValue({ data: solde })

    mount({ route: '/?onglet=postes' })

    // Le poste SOLDÉ affiche son écart réalisé, tel que le serveur l'a calculé.
    expect((await screen.findAllByText('FAC-2026-0212')).length)
      .toBeGreaterThan(0)

    const ligne = (await screen.findAllByText(ouvert.document_reference))
      .map((el) => el.closest('tr')).find(Boolean)
    await userEvent.click(
      within(ligne).getByLabelText("Plus d'actions sur la ligne"))
    await userEvent.click(await screen.findByRole(
      'menuitem', { name: /Constater l'écart de change/i }))

    fireEvent.change(screen.getByLabelText(/Date de règlement/), {
      target: { value: '2026-08-14' },
    })
    fireEvent.change(screen.getByLabelText(/Taux de règlement/), {
      target: { value: '11.10' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Constater l'écart/ }))

    await waitFor(() => {
      expect(mocks.constaterEcart).toHaveBeenCalledWith(ouvert.id, {
        date_reglement: '2026-08-14', taux_reglement: '11.10',
      })
    })
  }, 30000)
})

describe('DevisesPage — réévaluation de clôture (XACC18)', () => {
  it('lance le run et affiche le détail par poste renvoyé par le serveur', async () => {
    mocks.tauxList.mockResolvedValue({ data: [] })
    mocks.postesList.mockResolvedValue({ data: [] })
    mocks.reevaluationsList.mockResolvedValue({ data: [] })
    mocks.lancer.mockResolvedValue({
      data: {
        id: 7, date_cloture: '2026-12-31', date_extourne: '2027-01-01',
        ecriture: 9100, ecriture_extourne: 9101, total_ecart: '5000.00',
        lignes: [{ id: 12, item: 88, document_reference: 'FAC-901',
          devise: 'EUR', taux_cloture: '10.500000', ecart: '5000.00' }],
        date_creation: '2026-12-31T18:00:00Z',
      },
    })

    mount({ route: '/?onglet=reevaluations' })

    // `selector: 'input'` : « Date de clôture » est AUSSI l'en-tête triable de
    // la colonne du tableau — sans ce filtre, la requête trouve deux éléments.
    fireEvent.change(
      await screen.findByLabelText(/Date de clôture/, { selector: 'input' }),
      { target: { value: '2026-12-31' } })
    fireEvent.click(screen.getByRole('button', { name: 'Lancer' }))

    await waitFor(() => {
      expect(mocks.lancer).toHaveBeenCalledWith({ date_cloture: '2026-12-31' })
    })
    await waitFor(() => {
      expect(screen.getByText(/Détail — clôture du/)).toBeInTheDocument()
    })
    expect(screen.getByText('FAC-901')).toBeInTheDocument()
  }, 30000)
})
