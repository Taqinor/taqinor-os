import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import CONTRAT from '../../../../backend/django_core/apps/sav/contract_samples/piece_retiree.json'

// ASAV10 — champ « N° de série du neuf » dans « Retirer une pièce ». Faux
// serveur construit sur le contrat partagé piece_retiree.json (ASAV1) : il ne
// crée un équipement neuf QUE si le corps porte `serie_neuve`.

const serveur = vi.hoisted(() => ({ corps: [], parc: [] }))

vi.mock('../../features/sav/store/ticketsSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, updateTicket: () => {
    const action = { type: 'sav/updateTicket/noop' }
    action.unwrap = () => Promise.resolve({})
    return action
  } }
})

vi.mock('../../api/savApi', () => ({
  default: {
    getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketPieces: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: serveur.parc })),
    getTicketPiecesUnifiees: vi.fn(() => Promise.resolve({
      data: { lignes: [], sous_totaux: { ajout: 0, retrait: 0, recyclage: 0 } } })),
    retirerTicketPiece: vi.fn((id, body) => {
      serveur.corps.push(body)
      if (body.serie_neuve === 'DEJA-AU-PARC') {
        return Promise.reject({ response: { status: 400, data: CONTRAT.exemple_400_serie_neuve } })
      }
      if (body.serie_neuve) {
        serveur.parc.push(CONTRAT.exemple.equipement_neuf)
        return Promise.resolve({ data: CONTRAT.exemple })
      }
      return Promise.resolve({ data: CONTRAT.exemple_sans_serie_neuve })
    }),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn((url) => Promise.resolve({
    data: url === '/stock/produits/' ? [{ id: 1450, nom: 'Onduleur Deye', sku: 'DEYE' }] : [] })) },
}))
vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'

afterEach(() => { cleanup(); serveur.corps.length = 0; serveur.parc.length = 0 })

function renderDetail() {
  const store = configureStore({ reducer: {
    tickets: (state = { items: [] }) => state,
    auth: (state = { role: 'admin', permissions: [] }) => state,
  } })
  const ticket = { id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
    priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
    couverture: 'a_determiner', installation: 208, devis_id_ext: null, facture_id_ext: null,
    instructions: '' }
  return render(<Provider store={store}><MemoryRouter>
    <TicketDetail ticket={ticket} onClose={() => {}} onSaved={() => {}} />
  </MemoryRouter></Provider>)
}

async function choisirProduit(user) {
  await user.click(screen.getByRole('combobox', { name: 'Produit à retirer' }))
  await user.click(await screen.findByText('Onduleur Deye (DEYE)'))
}

describe('TicketDetail — ASAV10 série du neuf au retrait', () => {
  it('une série neuve crée l\'équipement neuf, affiché et présent au parc', async () => {
    const user = userEvent.setup()
    renderDetail()
    await choisirProduit(user)
    await user.type(screen.getByLabelText(/N° de série du neuf/), 'DEYE-SUN8K-2609-0031', { delay: null })
    await user.click(screen.getByRole('button', { name: /Retirer une pièce/ }))
    expect(await screen.findByTestId('equipement-neuf')).toHaveTextContent('DEYE-SUN8K-2609-0031')
    await waitFor(() => expect(serveur.parc).toHaveLength(1))
  }, 60000)

  it('sans série neuve : retrait seul, aucun équipement neuf', async () => {
    const user = userEvent.setup()
    renderDetail()
    await choisirProduit(user)
    await user.click(screen.getByRole('button', { name: /Retirer une pièce/ }))
    await waitFor(() => expect(serveur.corps).toHaveLength(1))
    expect(screen.queryByTestId('equipement-neuf')).toBeNull()
    expect(serveur.parc).toHaveLength(0)
  }, 60000)

  it('400 serie_neuve affiché sous le champ', async () => {
    const user = userEvent.setup()
    renderDetail()
    await choisirProduit(user)
    await user.type(screen.getByLabelText(/N° de série du neuf/), 'DEJA-AU-PARC', { delay: null })
    await user.click(screen.getByRole('button', { name: /Retirer une pièce/ }))
    expect(await screen.findByText(/déjà au parc/)).toBeInTheDocument()
    expect(serveur.parc).toHaveLength(0)
  }, 60000)
})
