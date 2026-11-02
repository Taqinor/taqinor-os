import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* NTCRM15 — widget dashboard « Comptes à réactiver » (comptes dormants,
   NTCRM14). Liste + bouton one-click de relance. crmApi mocké. */

vi.mock('../parametres/ReglesAttributionEditor', () => ({ default: () => null }))
vi.mock('../../api/crmApi', () => ({
  default: {
    // CADV105 — file « À prendre » de l'écran d'attribution.
    getDispatch: vi.fn(),
    attribuerLead: vi.fn(),
    saveReglagesDispatch: vi.fn(),
    getComptesDormants: vi.fn(() => Promise.resolve({
      data: {
        seuil: 90,
        count: 1,
        results: [{ id: 42, nom: 'Client froid', derniere_activite: '2026-01-01', jours_inactivite: 100 }],
      },
    })),
    relancerDormance: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  },
}))

import crmApi from '../../api/crmApi'
import DormantAccountsWidget from './DormantAccountsWidget'
import AttributionLeadsPage from './AttributionLeadsPage'
import { exempleContrat } from '../../test/fixtures/contractSamples'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <DormantAccountsWidget />
    </MemoryRouter>,
  )
}

describe('DormantAccountsWidget (NTCRM15)', () => {
  it('liste les comptes dormants réels', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Client froid')).toBeInTheDocument())
    expect(screen.getByText('100 j sans activité')).toBeInTheDocument()
  })

  it('le bouton crée une activité de relance', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Client froid')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Créer une relance'))
    await waitFor(() => expect(crmApi.relancerDormance).toHaveBeenCalledWith(42))
    await waitFor(() => expect(screen.getByText('Relancé')).toBeInTheDocument())
  })

  it('affiche un état vide quand aucun compte n\'est dormant', async () => {
    crmApi.getComptesDormants.mockResolvedValueOnce({ data: { seuil: 90, count: 0, results: [] } })
    mount()
    await waitFor(() => expect(screen.getByText(/Aucun compte dormant/)).toBeInTheDocument())
  })
})

/* CADV105 (D-CADV-7) — file « À prendre » : un simple membre voit les leads libres et
   s'en attribue un LUI-MÊME. Charge utile = le contrat `dispatch_leads.json`. */
const MON_ID = 9
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
    render(<Provider store={configureStore({ reducer: { auth: (s = { user: { id: MON_ID } }) => s } })}><AttributionLeadsPage /></Provider>)
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
    render(<Provider store={configureStore({ reducer: { auth: (s = { user: { id: MON_ID } }) => s } })}><AttributionLeadsPage /></Provider>)
    const file = await screen.findByTestId('file-a-prendre')

    await userEvent.click(within(file).getAllByRole('button', { name: 'Je le prends' })[0])

    expect(await screen.findByText('Déjà pris')).toBeInTheDocument()
    await waitFor(() => expect(within(file).getAllByRole('button', { name: 'Je le prends' })).toHaveLength(2))
  })

  it('hors file « À prendre » : aucune section', async () => {
    crmApi.getDispatch.mockResolvedValue({ data: BASE })
    render(<Provider store={configureStore({ reducer: { auth: (s = { user: { id: MON_ID } }) => s } })}><AttributionLeadsPage /></Provider>)
    await screen.findByText(PREMIER.nom, { selector: 'h2' })
    expect(screen.queryByTestId('file-a-prendre')).not.toBeInTheDocument()
  })
})
