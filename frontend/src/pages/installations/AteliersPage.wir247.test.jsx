import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR247 — 8 exports atelier orphelins (gamme d'exécution, lignes de
   composant, quantité récupérée, nomenclature) ont enfin un appelant :
   getEtapesAssemblage / cocherEtapeAssemblage / getLignesAssemblage /
   createLigneAssemblage / updateLigneAssemblage / deleteLigneAssemblage /
   updateLigneDemontage / getKitStructure. */

const api = vi.hoisted(() => ({
  getOrdresAssemblage: vi.fn(),
  getOrdresDemontage: vi.fn(),
  getKitsAssemblage: vi.fn(),
  getDisponibiliteAssemblage: vi.fn(),
  getControleQualiteAssemblage: vi.fn(),
  getHistoriqueAssemblage: vi.fn(),
  getEtapesAssemblage: vi.fn(),
  cocherEtapeAssemblage: vi.fn(),
  getLignesAssemblage: vi.fn(),
  createLigneAssemblage: vi.fn(),
  updateLigneAssemblage: vi.fn(),
  deleteLigneAssemblage: vi.fn(),
  updateLigneDemontage: vi.fn(),
  getKitStructure: vi.fn(),
  bonAssemblageUrl: (id) => `/api/x/${id}/bon-pdf/`,
}))
vi.mock('../../api/installationsApi', () => ({ default: api }))

import AteliersPage from './AteliersPage'

const ORDRE = {
  id: 1, reference: 'ASM-001', kit: 3, kit_nom: 'Kit onduleur', quantite: 2,
  statut: 'planifie', date_creation: '2026-01-01', lignes: [],
}
const ORDRE_EN_COURS = { ...ORDRE, id: 2, reference: 'ASM-002', statut: 'en_cours' }

const LIGNE = { id: 11, ordre: 1, produit_nom: 'Onduleur 5kW', quantite: '2', origine: 'kit' }
const ETAPE = {
  id: 21, ordre: 1, etape_modele: 7, libelle: 'Câblage DC',
  duree_attendue_min: 45, fait: false, duree_reelle_min: null,
}
const DEMONTAGE = {
  id: 9, reference: 'DSM-001', kit_nom: 'Kit batterie', quantite: 1,
  statut: 'planifie', date_creation: '2026-01-02',
  lignes: [{
    id: 31, produit_nom: 'Batterie 5kWh', quantite_attendue: '4',
    quantite_recuperee: null,
  }],
}

function renderPage(role = 'responsable') {
  const store = configureStore({ reducer: { auth: (state = { role }) => state } })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><AteliersPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

async function ouvrirOrdre(user, reference, container) {
  await waitFor(() => expect(container.querySelector('[data-dt-table]')).not.toBeNull())
  const table = within(container.querySelector('[data-dt-table]'))
  await user.click(await table.findByText(reference))
  return screen.findByRole('dialog')
}

beforeEach(() => {
  api.getOrdresAssemblage.mockResolvedValue({ data: [ORDRE, ORDRE_EN_COURS] })
  api.getOrdresDemontage.mockResolvedValue({ data: [DEMONTAGE] })
  api.getKitsAssemblage.mockResolvedValue({ data: [] })
  api.getDisponibiliteAssemblage.mockResolvedValue({ data: [] })
  api.getControleQualiteAssemblage.mockResolvedValue({ data: [] })
  api.getHistoriqueAssemblage.mockResolvedValue({ data: [] })
  api.getEtapesAssemblage.mockResolvedValue({ data: [ETAPE] })
  api.getLignesAssemblage.mockResolvedValue({ data: [LIGNE] })
  // Le serveur renvoie l'étape telle qu'il vient de l'écrire : on reflète la
  // charge envoyée, sinon l'état local repart d'une valeur qui n'est pas la
  // sienne.
  api.cocherEtapeAssemblage.mockImplementation(
    (id, modele, payload) => Promise.resolve({ data: { ...ETAPE, ...payload } }))
  api.updateLigneAssemblage.mockResolvedValue({ data: { ...LIGNE, quantite: '5' } })
  api.createLigneAssemblage.mockResolvedValue({
    data: { id: 12, ordre: 1, designation: 'Câble 6mm²', quantite: '30' },
  })
  api.deleteLigneAssemblage.mockResolvedValue({ data: {} })
  api.updateLigneDemontage.mockResolvedValue({
    data: { ...DEMONTAGE.lignes[0], quantite_recuperee: '3' },
  })
  api.getKitStructure.mockResolvedValue({
    data: {
      kit_id: 3,
      composants: [
        { niveau: 0, type: 'produit', produit_id: 5, designation: 'Onduleur 5kW', quantite: '1' },
        { niveau: 1, type: 'produit', produit_id: 6, designation: 'Câble DC', quantite: '2' },
      ],
    },
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AteliersPage — WIR247 gamme, lignes, nomenclature', () => {
  it('charge la gamme d’exécution et coche une étape avec sa durée réelle', async () => {
    const user = userEvent.setup()
    const { container } = renderPage()
    await ouvrirOrdre(user, 'ASM-001', container)

    await waitFor(() => expect(api.getEtapesAssemblage).toHaveBeenCalledWith(1))
    const gamme = within(await screen.findByTestId('atelier-gamme'))
    expect(gamme.getByText('Câblage DC')).toBeInTheDocument()

    const duree = gamme.getByLabelText('Durée réelle de Câblage DC')
    await user.type(duree, '52')
    await user.tab()
    await waitFor(() => expect(api.cocherEtapeAssemblage).toHaveBeenCalledWith(
      1, 7, { fait: false, duree_reelle_min: '52' }))

    await user.click(gamme.getByLabelText('Étape faite : Câblage DC'))
    await waitFor(() => expect(api.cocherEtapeAssemblage).toHaveBeenCalledWith(
      1, 7, { fait: true, duree_reelle_min: '52' }))
  })

  it('édite, ajoute et retire une ligne de composant tant que l’ordre est PLANIFIÉ', async () => {
    const user = userEvent.setup()
    const { container } = renderPage()
    await ouvrirOrdre(user, 'ASM-001', container)

    await waitFor(() => expect(api.getLignesAssemblage).toHaveBeenCalledWith(1))
    const bloc = within(await screen.findByTestId('atelier-lignes-editables'))

    const qte = bloc.getByLabelText('Quantité pour Onduleur 5kW')
    await user.clear(qte)
    await user.type(qte, '5')
    await user.tab()
    await waitFor(() => expect(api.updateLigneAssemblage).toHaveBeenCalledWith(
      11, { quantite: '5' }))

    await user.type(bloc.getByLabelText('Composant à ajouter'), 'Câble 6mm²')
    await user.type(bloc.getByLabelText('Quantité de la ligne à ajouter'), '30')
    await user.click(bloc.getByRole('button', { name: 'Ajouter la ligne' }))
    await waitFor(() => expect(api.createLigneAssemblage).toHaveBeenCalledWith(
      { ordre: 1, designation: 'Câble 6mm²', quantite: '30' }))

    await user.click(bloc.getAllByRole('button', { name: 'Retirer' })[0])
    await waitFor(() => expect(api.deleteLigneAssemblage).toHaveBeenCalledWith(11))
  })

  it('l’édition des lignes DISPARAÎT une fois l’ordre démarré', async () => {
    const user = userEvent.setup()
    const { container } = renderPage()
    await ouvrirOrdre(user, 'ASM-002', container)

    await waitFor(() => expect(api.getLignesAssemblage).toHaveBeenCalledWith(2))
    expect(screen.queryByTestId('atelier-lignes-editables')).toBeNull()
  })

  it('ouvre la nomenclature indentée du kit (aucun coût, aucune marge)', async () => {
    const user = userEvent.setup()
    const { container } = renderPage()
    const dialog = await ouvrirOrdre(user, 'ASM-001', container)

    await user.click(within(dialog).getByRole('button', { name: /Nomenclature/ }))
    await waitFor(() => expect(api.getKitStructure).toHaveBeenCalledWith(3))
    const nomenclature = await screen.findByTestId('atelier-nomenclature')
    expect(nomenclature).toHaveTextContent('Onduleur 5kW')
    expect(nomenclature).toHaveTextContent('Câble DC')
    // GARDE MARGE : l'atelier n'affiche NI coût NI marge.
    expect(nomenclature.textContent).not.toMatch(/marge|coût|cout/i)
  })
})

describe('AteliersPage — WIR247 quantité récupérée au démontage', () => {
  it('enregistre la quantité récupérée ligne à ligne avant clôture', async () => {
    const user = userEvent.setup()
    const { container } = renderPage()
    await waitFor(() => expect(api.getOrdresDemontage).toHaveBeenCalled())
    await user.click(screen.getByRole('radio', { name: 'Démontage' }))
    await ouvrirOrdre(user, 'DSM-001', container)

    const champ = await screen.findByLabelText('Quantité récupérée pour Batterie 5kWh')
    await user.type(champ, '3')
    await user.tab()
    await waitFor(() => expect(api.updateLigneDemontage).toHaveBeenCalledWith(
      31, { quantite_recuperee: '3' }))
  })
})
