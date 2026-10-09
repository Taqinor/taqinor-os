import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import CONTRAT from '../../../../backend/django_core/apps/sav/contract_samples/piece_retiree.json'

// ASAV10 — champ « N° de série du neuf » dans « Retirer une pièce ». Faux
// serveur construit sur le contrat partagé piece_retiree.json (ASAV1) : il ne
// crée un équipement neuf QUE si le corps porte `serie_neuve`.

const serveur = vi.hoisted(() => ({ corps: [], parc: [] }))

vi.mock('../../features/sav/store/ticketsSlice', async (io) => (await import('./__testutils__/ticketDetailMocks.js')).ticketsSliceMock(await io()))

vi.mock('../../api/savApi', async () => (await import('./__testutils__/ticketDetailMocks.js')).savApiMock({
  getEquipements: vi.fn(() => Promise.resolve({ data: serveur.parc })),
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
}))

vi.mock('../../api/axios', async () => (await import('./__testutils__/ticketDetailMocks.js')).axiosMock((url) => Promise.resolve({
  data: url === '/stock/produits/' ? [{ id: 1450, nom: 'Onduleur Deye', sku: 'DEYE' }] : [] })))
vi.mock('../../api/installationsApi', async () => (await import('./__testutils__/ticketDetailMocks.js')).installationsApiMock())

import { TicketDetail } from './TicketsPage'
import { ticketStore, TICKET_BASE } from './__testutils__/ticketDetailMocks.js'

afterEach(() => { cleanup(); serveur.corps.length = 0; serveur.parc.length = 0 })

function renderDetail() {
  const ticket = { ...TICKET_BASE, installation: 208 }
  return render(<Provider store={ticketStore('admin')}><MemoryRouter>
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
