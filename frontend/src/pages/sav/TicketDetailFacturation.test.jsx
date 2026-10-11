import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* XSAV3/XFSM1/XCTR4 — boutons « Créer un devis » / « Générer facture » /
   « Facturer » sur le détail du ticket SAV, gatés sur la garantie/couverture
   calculée côté serveur. savApi + api (axios direct) + installationsApi
   mockés — aucun réseau réel. */

vi.mock('../../features/sav/store/ticketsSlice', async (importOriginal) =>
  (await import('./__tests__/ticketDetailTestKit')).ticketsSliceNoopMock(importOriginal))

vi.mock('../../api/savApi', async () => (await import('./__tests__/ticketDetailTestKit')).savApiDetailMock({
  creerDevisTicket: vi.fn(() => Promise.resolve({
    data: { devis_id: 42, devis_reference: 'DEV-SAV-42' },
  })),
  facturerTicket: vi.fn(() => Promise.resolve({
    data: { facture_id: 8, facture_reference: 'FACT-SAV-8', couverture: 'facturable' },
  })),
  rapportPdf: vi.fn(() => Promise.resolve({ data: new Blob() })),
}))

vi.mock('../../api/axios', async () => (await import('./__tests__/ticketDetailTestKit')).axiosVideMock())

vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailTestKit')).installationsApiVideMock())

import { TicketDetail } from './TicketsPage'
import { renderTicketDetail } from './__tests__/ticketDetailTestKit'
import savApi from '../../api/savApi'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderDetail = (ticket, opts) =>
  renderTicketDetail(TicketDetail, ticket, opts, { routeur: false })

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
  it('propose « Facturer » (routage de couverture) une fois la couverture posée', async () => {
    renderDetail({ ...baseTicket, couverture: 'facturable' })
    const btn = await screen.findByRole('button', { name: /^Facturer$/ })
    fireEvent.click(btn)
    await waitFor(() => expect(savApi.facturerTicket).toHaveBeenCalledWith(1, false))
    expect(await screen.findByText('Facture générée')).toBeInTheDocument()
  })

  it('affiche un badge si la facture existe déjà (idempotence UI)', async () => {
    renderDetail({ ...baseTicket, facture_id_ext: 5 })
    expect(await screen.findByText('Facture générée')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Facturer/ })).not.toBeInTheDocument()
  })
})
