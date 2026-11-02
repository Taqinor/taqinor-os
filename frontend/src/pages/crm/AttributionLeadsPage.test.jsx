import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* CADV105 (D-CADV-7) — la file « À prendre » de l'écran d'attribution : un simple
   membre voit les leads libres et s'en attribue un LUI-MÊME. Charge utile = le
   contrat `dispatch_leads.json` (équipe en file `a_prendre`, deux leads). */
import { exempleContrat } from '../../test/fixtures/contractSamples'

const MON_ID = 9
vi.mock('react-redux', () => ({
  useSelector: (fn) => fn({ auth: { user: { id: 9 } } }),
}))
vi.mock('../../api/crmApi', () => ({
  default: {
    getDispatch: vi.fn(),
    attribuerLead: vi.fn(),
    saveReglagesDispatch: vi.fn(),
  },
}))
vi.mock('../parametres/ReglesAttributionEditor', () => ({ default: () => null }))

import crmApi from '../../api/crmApi'
import AttributionLeadsPage from './AttributionLeadsPage'

const BASE = exempleContrat('crm', 'dispatch_leads')
const PREMIER = BASE.leads[0]
const SECOND = { ...PREMIER, id: PREMIER.id + 1, nom: 'Samira Idrissi' }

const serveur = (leads) => ({
  data: {
    ...BASE,
    equipe: { ...BASE.equipe, a_prendre: true },
    en_attente: leads.length,
    leads,
    equipes_reglables: [],
  },
})

describe('AttributionLeadsPage — file « À prendre »', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('un clic sur « Je le prends » attribue le lead à SOI-MÊME, puis le lead disparaît de la liste', async () => {
    crmApi.getDispatch
      .mockResolvedValueOnce(serveur([PREMIER, SECOND]))
      .mockResolvedValue(serveur([SECOND]))
    crmApi.attribuerLead.mockResolvedValue({ data: {} })
    render(<AttributionLeadsPage />)
    const file = await screen.findByTestId('file-a-prendre')
    const boutons = within(file).getAllByRole('button', { name: 'Je le prends' })
    expect(boutons).toHaveLength(2)

    await userEvent.click(boutons[0])

    await waitFor(() => expect(crmApi.attribuerLead).toHaveBeenCalledWith(PREMIER.id, MON_ID))
    expect(await within(file).findByText(`Pris par vous : ${PREMIER.nom}`)).toBeInTheDocument()
    await waitFor(() => expect(within(file).getAllByRole('button', { name: 'Je le prends' })).toHaveLength(1))
    expect(within(file).getByText(SECOND.nom)).toBeInTheDocument()
  })

  it('un 409 affiche « Déjà pris » sans casser la liste', async () => {
    crmApi.getDispatch.mockResolvedValue(serveur([PREMIER, SECOND]))
    crmApi.attribuerLead.mockRejectedValue({ response: { status: 409 } })
    render(<AttributionLeadsPage />)
    const file = await screen.findByTestId('file-a-prendre')

    await userEvent.click(within(file).getAllByRole('button', { name: 'Je le prends' })[0])

    expect(await screen.findByText('Déjà pris')).toBeInTheDocument()
    await waitFor(() => expect(within(file).getAllByRole('button', { name: 'Je le prends' })).toHaveLength(2))
  })

  it('hors file « À prendre » : aucune section', async () => {
    crmApi.getDispatch.mockResolvedValue({ data: BASE })
    render(<AttributionLeadsPage />)
    await screen.findByText(PREMIER.nom, { selector: 'h2' })
    expect(screen.queryByTestId('file-a-prendre')).not.toBeInTheDocument()
  })
})
