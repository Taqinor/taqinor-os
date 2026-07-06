import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* XSAV3/XFSM1/XCTR4 — boutons « Créer un devis » / « Générer facture » /
   « Facturer » sur le détail du ticket SAV, gatés sur la garantie/couverture
   calculée côté serveur. savApi + api (axios direct) + installationsApi
   mockés — aucun réseau réel. */

vi.mock('../../features/sav/store/ticketsSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    updateTicket: () => {
      const action = { type: 'sav/updateTicket/noop' }
      action.unwrap = () => Promise.resolve({})
      return action
    },
  }
})

vi.mock('../../api/savApi', () => ({
  default: {
    getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketPieces: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    creerDevisTicket: vi.fn(() => Promise.resolve({
      data: { devis_id: 42, devis_reference: 'DEV-SAV-42' },
    })),
    genererFactureTicket: vi.fn(() => Promise.resolve({
      data: { facture_id: 7, facture_reference: 'FACT-SAV-7', sous_garantie: false },
    })),
    facturerTicket: vi.fn(() => Promise.resolve({
      data: { facture_id: 8, facture_reference: 'FACT-SAV-8', couverture: 'facturable' },
    })),
    rapportPdf: vi.fn(() => Promise.resolve({ data: new Blob() })),
    // XSAV12/21/27/28, ZSAV8/9 — TicketAdvancedPanel (montée dans TicketDetail).
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })) },
}))

vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'
import savApi from '../../api/savApi'

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
      <TicketDetail ticket={ticket} onClose={() => {}} onSaved={() => {}} {...opts} />
    </Provider>,
  )
}

const baseTicket = {
  id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
  priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
  couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null,
}

describe('TicketDetail — XSAV3 création de devis de réparation', () => {
  it('affiche « Créer un devis » pour un ticket hors garantie et crée le devis', async () => {
    renderDetail(baseTicket)
    const btn = await screen.findByRole('button', { name: /Créer un devis/ })
    fireEvent.click(btn)
    await waitFor(() => expect(savApi.creerDevisTicket).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Devis créé')).toBeInTheDocument()
  })

  it('ne propose pas de devis pour un ticket sous garantie', async () => {
    renderDetail({ ...baseTicket, sous_garantie_effectif: 'oui' })
    await screen.findByText('Ticket SAV — SAV-1', { exact: false })
    expect(screen.queryByRole('button', { name: /Créer un devis/ })).not.toBeInTheDocument()
  })

  it('affiche un badge si le devis existe déjà (idempotence UI)', async () => {
    renderDetail({ ...baseTicket, devis_id_ext: 99 })
    expect(await screen.findByText('Devis créé')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Créer un devis/ })).not.toBeInTheDocument()
  })
})

describe('TicketDetail — XFSM1/XCTR4 facturation', () => {
  it('propose « Générer facture » (repli générique) tant que la couverture est à déterminer', async () => {
    renderDetail(baseTicket)
    const btn = await screen.findByRole('button', { name: /Générer facture/ })
    fireEvent.click(btn)
    await waitFor(() => expect(savApi.genererFactureTicket).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Facture générée')).toBeInTheDocument()
  })

  it('propose « Facturer » (routage de couverture) une fois la couverture posée', async () => {
    renderDetail({ ...baseTicket, couverture: 'facturable' })
    const btn = await screen.findByRole('button', { name: /^Facturer$/ })
    fireEvent.click(btn)
    await waitFor(() => expect(savApi.facturerTicket).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Facture générée')).toBeInTheDocument()
  })

  it('affiche un badge si la facture existe déjà (idempotence UI)', async () => {
    renderDetail({ ...baseTicket, facture_id_ext: 5 })
    expect(await screen.findByText('Facture générée')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Facturer/ })).not.toBeInTheDocument()
  })
})
