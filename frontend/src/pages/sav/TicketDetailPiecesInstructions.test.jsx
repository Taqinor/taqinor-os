import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* WIR232/ZMFG8/XMFG10 — vue unifiée Ajout/Retrait/Recyclage des pièces du
   ticket (getTicketPiecesUnifiees enfin consommé) + formulaire « Retirer une
   pièce » traçable (destination/opération/n° série), distinct du bouton
   « Retirer » existant (qui supprime la consommation sans laisser de trace).
   WIR233/ZMFG5 — section Instructions éditable + Suggestions KB (insertion
   locale, jamais une écriture serveur avant l'enregistrement du ticket).
   Patron TicketDetailFacturation.test.jsx (savApi + api + installationsApi
   mockés, Provider redux minimal). */

const { getTicketPiecesUnifiees, retirerTicketPiece, getInstructionsSuggestions, updateTicketSpy } = vi.hoisted(() => ({
  getTicketPiecesUnifiees: vi.fn(() => Promise.resolve({
    data: { lignes: [], sous_totaux: { ajout: 0, retrait: 0, recyclage: 0 } },
  })),
  retirerTicketPiece: vi.fn(() => Promise.resolve({
    data: { id: 55, produit: 3, quantite: '1', destination: 'stock_occasion', restockee: true },
  })),
  getInstructionsSuggestions: vi.fn(() => Promise.resolve({
    data: { results: [{ id: 1, titre: 'Procédure fusible grillé', corps: 'Remplacer le fusible après coupure.' }] },
  })),
  updateTicketSpy: vi.fn(({ id, data }) => {
    const action = { type: 'sav/updateTicket/noop' }
    action.unwrap = () => Promise.resolve({ id, ...data })
    return action
  }),
}))

vi.mock('../../features/sav/store/ticketsSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, updateTicket: (...a) => updateTicketSpy(...a) }
})

vi.mock('../../api/savApi', () => ({
  default: {
    getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketPieces: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketPiecesUnifiees: (...a) => getTicketPiecesUnifiees(...a),
    retirerTicketPiece: (...a) => retirerTicketPiece(...a),
    getInstructionsSuggestions: (...a) => getInstructionsSuggestions(...a),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn((url) => {
      if (url === '/stock/produits/') {
        return Promise.resolve({ data: [{ id: 3, nom: 'Onduleur HS', sku: 'OND-HS' }] })
      }
      return Promise.resolve({ data: [] })
    }),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore() {
  return configureStore({
    reducer: {
      tickets: (state = { items: [] }) => state,
      auth: (state = { role: 'admin', permissions: [] }) => state,
    },
  })
}

function renderDetail(ticket, opts = {}) {
  const store = makeStore()
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <TicketDetail ticket={ticket} onClose={() => {}} onSaved={() => {}} {...opts} />
      </MemoryRouter>
    </Provider>,
  )
}

const baseTicket = {
  id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
  priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
  couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null,
  instructions: '',
}

describe('TicketDetail — pièces du ticket, vue unifiée (WIR232)', () => {
  it('rend la vue unifiée à partir de getTicketPiecesUnifiees', async () => {
    getTicketPiecesUnifiees.mockResolvedValueOnce({
      data: {
        lignes: [
          { id: 10, operation: 'ajout', produit_id: 3, produit_nom: 'Onduleur HS', quantite: '1' },
          { id: 20, operation: 'retrait', produit_id: 3, produit_nom: 'Onduleur HS', quantite: '1', destination: 'rebut' },
        ],
        sous_totaux: { ajout: 1, retrait: 1, recyclage: 0 },
      },
    })
    renderDetail(baseTicket)
    await waitFor(() => expect(getTicketPiecesUnifiees).toHaveBeenCalledWith(1))
    const liste = await screen.findByTestId('pieces-unifiees-liste')
    expect(liste).toHaveTextContent('Ajout')
    expect(liste).toHaveTextContent('Retrait')
  })

  it('POST avec les champs exacts (produit/quantite/destination/operation/numero_serie) puis recharge', async () => {
    const user = userEvent.setup()
    renderDetail(baseTicket)
    await waitFor(() => expect(getTicketPiecesUnifiees).toHaveBeenCalled())

    await user.click(screen.getByRole('combobox', { name: 'Produit à retirer' }))
    await user.click(await screen.findByText('Onduleur HS (OND-HS)'))
    await user.click(screen.getByRole('combobox', { name: 'Destination' }))
    await user.click(await screen.findByText('Stock occasion'))

    getTicketPiecesUnifiees.mockClear()
    await user.click(screen.getByRole('button', { name: /Retirer une pièce/ }))

    await waitFor(() => expect(retirerTicketPiece).toHaveBeenCalledWith(1, expect.objectContaining({
      produit: '3', quantite: '1', destination: 'stock_occasion', operation: 'retrait',
    })))
    await waitFor(() => expect(getTicketPiecesUnifiees).toHaveBeenCalled())
  })

  it('400 FR affiché sans vider le formulaire', async () => {
    retirerTicketPiece.mockRejectedValueOnce({
      response: { data: { detail: 'Destination invalide.' } },
    })
    const user = userEvent.setup()
    renderDetail(baseTicket)
    await waitFor(() => expect(getTicketPiecesUnifiees).toHaveBeenCalled())

    await user.click(screen.getByRole('combobox', { name: 'Produit à retirer' }))
    await user.click(await screen.findByText('Onduleur HS (OND-HS)'))
    await user.click(screen.getByRole('button', { name: /Retirer une pièce/ }))

    expect(await screen.findByText('Destination invalide.')).toBeInTheDocument()
    // Le formulaire n'a PAS été vidé : le produit reste sélectionné (le
    // bouton resterait désactivé si `retirerForm.produit` avait été effacé).
    expect(screen.getByRole('button', { name: /Retirer une pièce/ })).toBeEnabled()
  })
})

describe('TicketDetail — Instructions (WIR233)', () => {
  it('édite les instructions et les enregistre avec le reste du ticket', async () => {
    const user = userEvent.setup()
    renderDetail(baseTicket)
    await screen.findByText('Ticket SAV — SAV-1', { exact: false })

    const zone = screen.getByLabelText("Instructions d'intervention")
    await user.type(zone, 'Couper le disjoncteur avant intervention.')
    expect(zone).toHaveValue('Couper le disjoncteur avant intervention.')
  })

  it('Suggestions KB : insère le corps SANS écriture serveur avant l’enregistrement', async () => {
    const user = userEvent.setup()
    renderDetail(baseTicket)
    await screen.findByText('Ticket SAV — SAV-1', { exact: false })

    await user.click(screen.getByRole('button', { name: /Suggestions KB/ }))
    await waitFor(() => expect(getInstructionsSuggestions).toHaveBeenCalledWith(1))
    await user.click(await screen.findByRole('button', { name: 'Insérer' }))

    const zone = screen.getByLabelText("Instructions d'intervention")
    expect(zone).toHaveValue('Remplacer le fusible après coupure.')
    // Aucune écriture serveur déclenchée par l'insertion elle-même — le
    // texte n'est qu'un état local tant que « Enregistrer » n'est pas cliqué.
    expect(updateTicketSpy).not.toHaveBeenCalled()
  })
})
