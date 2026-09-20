/* CAL184 — la case « Calepinage » du dialogue PDF de la liste des devis.

   Ce qui est prouvé ici : le TRI-ÉTAT (auto / oui / non) arrive TEL QUEL dans
   le corps envoyé à `generer-pdf`, donc à la whitelist `clean_pdf_options`
   (CAL183) — et l'écran n'invente aucune valeur par défaut : à l'ouverture,
   l'option vaut 'auto', qui s'envoie `null`.

   Le NOMBRE DE PAGES du PDF n'est pas vérifiable ici (il se décide dans le
   moteur vendorisé, côté serveur) : il l'est par `apps/ventes/tests/
   test_quote_engine_formats.py::TestPageCalepinage`, qui rend réellement le
   document. Ce test-ci prouve le chaînon qui manquait — l'option EST ENVOYÉE.

   Fichier dédié : le mock module-level de `genererPdfDevis` dans
   `DevisList.test.jsx` jette ses arguments (il ne rend qu'une action
   « thunk-like »), et on a besoin ici de les CAPTURER.
*/
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, within, cleanup, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

const genererPdfSpy = vi.fn()

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }),
    genererPdfDevis: (payload) => {
      genererPdfSpy(payload)
      const action = { type: 'ventes/genererPdfDevis/noop' }
      action.unwrap = () => Promise.resolve()
      return action
    },
    convertirDevisEnBC: () => ({ type: 'ventes/convertirDevisEnBC/noop' }),
  }
})

vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      etatPdfDevis: vi.fn(() => Promise.resolve({
        data: { devis: 77, statut: 'en_cours', fichier_pdf: false, erreur: null, date: null },
      })),
      getVariantes: vi.fn(() => Promise.resolve({ data: [] })),
      historiqueDevis: vi.fn(() => Promise.resolve({ data: [] })),
    },
  }
})

vi.mock('../../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: { ...actual.default, getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })) },
  }
})

vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listSavedViews: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    createSavedView: vi.fn(() => Promise.resolve({ data: { id: 1, ecran: 'ventes.devis' } })),
    updateSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    deleteSavedView: vi.fn(() => Promise.resolve({})),
  },
}))

import DevisList from './DevisList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const DEVIS = {
  id: 77, reference: 'DEV-CAL184', client_nom: 'ACME', statut: 'brouillon',
  date_creation: '2026-09-20', total_ttc: 90000, nb_options: 1, version: 1,
  // Une ligne d'onduleur classifiable : sans elle l'écran rabat le format sur
  // « une page » (présélection gracieuse), et le bloc n'apparaîtrait pas.
  lignes: [{ id: 1, designation: 'Onduleur hybride 5kW', quantite: '1', prix_unitaire: '24000' }],
}

function rendre() {
  const store = configureStore({
    reducer: {
      ventes: (state = { devis: [DEVIS], loading: false, error: null }) => state,
      auth: (state = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => state,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/devis']}>
        <ThemeProvider><DevisList /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

async function ouvrirDialoguePdf() {
  rendre()
  const ligne = screen.getByText('DEV-CAL184').closest('tr')
  fireEvent.click(within(ligne).getByTitle('Générer le PDF (choix du format)'))
  return screen.findByRole('dialog')
}

const optionsEnvoyees = () => genererPdfSpy.mock.calls.at(-1)[0].options

beforeEach(() => { genererPdfSpy.mockClear() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CAL184 — case « Calepinage » du dialogue PDF', () => {
  it('le tri-état est proposé, et « Automatique » est la valeur d’ouverture', async () => {
    const dialog = await ouvrirDialoguePdf()
    const bloc = within(dialog).getByTestId('cal184-calepinage')
    for (const libelle of [/Automatique/, /Inclure la planche cotée/, /Ne pas inclure/]) {
      expect(within(bloc).getByText(libelle)).toBeInTheDocument()
    }
    fireEvent.click(within(dialog).getByRole('button', { name: /Générer/ }))
    // 'auto' s'envoie `null` : l'écran ne tranche pas à la place du serveur.
    expect(optionsEnvoyees().include_calepinage).toBeNull()
  })

  it('« Ne pas inclure » envoie false — l’opt-out explicite', async () => {
    const dialog = await ouvrirDialoguePdf()
    const bloc = within(dialog).getByTestId('cal184-calepinage')
    fireEvent.click(within(bloc).getByText(/Ne pas inclure/))
    fireEvent.click(within(dialog).getByRole('button', { name: /Générer/ }))
    expect(optionsEnvoyees().include_calepinage).toBe(false)
  })

  it('« Inclure la planche cotée » envoie true', async () => {
    const dialog = await ouvrirDialoguePdf()
    const bloc = within(dialog).getByTestId('cal184-calepinage')
    fireEvent.click(within(bloc).getByText(/Inclure la planche cotée/))
    fireEvent.click(within(dialog).getByRole('button', { name: /Générer/ }))
    expect(optionsEnvoyees().include_calepinage).toBe(true)
  })

  it('le choix ne touche AUCUNE autre option du corps envoyé', async () => {
    const dialog = await ouvrirDialoguePdf()
    fireEvent.click(within(dialog).getByRole('button', { name: /Générer/ }))
    const auto = { ...optionsEnvoyees() }

    cleanup()
    const dialog2 = await ouvrirDialoguePdf()
    fireEvent.click(within(within(dialog2).getByTestId('cal184-calepinage'))
      .getByText(/Ne pas inclure/))
    fireEvent.click(within(dialog2).getByRole('button', { name: /Générer/ }))
    const non = { ...optionsEnvoyees() }

    delete auto.include_calepinage
    delete non.include_calepinage
    expect(non).toEqual(auto)
  })
})
