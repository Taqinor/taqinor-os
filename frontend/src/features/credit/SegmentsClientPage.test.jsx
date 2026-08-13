import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* PACT50 — Rattachement d'un client à un segment crédit.

   Charges utiles alignées sur les sérialiseurs serveur réels
   (`SegmentClientCreditSerializer` : id/client/segment/date_modification,
   `ConditionPaiementSegmentSerializer` : id/segment/delai_paiement_jours/
   pct_acompte_defaut/mode_hold_override/dates) et sur le dictionnaire
   d'exposition `{count, resultats}` — jamais une forme inventée.

   Le critère : changer le segment d'un client fait apparaître LES CONDITIONS
   DU NOUVEAU SEGMENT (celles que `condition_paiement_client` résoudra pour son
   prochain devis), et un segment sans condition configurée est dit tel quel. */

vi.mock('../../api/creditApi', () => ({
  default: {
    getSegmentsClient: vi.fn(),
    getConditionsSegment: vi.fn(),
    getExposition: vi.fn(),
    createSegmentClient: vi.fn(),
    updateSegmentClient: vi.fn(),
    deleteSegmentClient: vi.fn(),
  },
}))

import creditApi from '../../api/creditApi'
import SegmentsClientPage from './SegmentsClientPage'

const CONDITIONS = [
  {
    id: 1, segment: 'standard', delai_paiement_jours: 30,
    pct_acompte_defaut: '40.00', mode_hold_override: '',
    date_creation: '2026-01-01T09:00:00Z', date_modification: '2026-01-01T09:00:00Z',
  },
  {
    id: 2, segment: 'grand_compte', delai_paiement_jours: 90,
    pct_acompte_defaut: '10.00', mode_hold_override: 'avertissement',
    date_creation: '2026-01-01T09:00:00Z', date_modification: '2026-01-01T09:00:00Z',
  },
]

const EXPOSITION = {
  count: 2,
  resultats: [
    {
      client_id: 7, client_nom: 'Villa Zenith', encours: '120000.00',
      limite: '400000.00', disponible: '280000.00', pct_utilise: 0.3,
      depasse: false, lettre_score: 'B', mode_hold: 'avertissement',
      garantie_assurance: null, depasse_garantie: false,
    },
    {
      client_id: 9, client_nom: 'Ferme Tadla', encours: '50000.00',
      limite: null, disponible: null, pct_utilise: null, depasse: false,
      lettre_score: 'A', mode_hold: null,
      garantie_assurance: null, depasse_garantie: false,
    },
  ],
}

const rattachement = (segment) => ([
  { id: 5, client: 7, segment, date_modification: '2026-08-01T09:00:00Z' },
])

const monter = () => render(
  <MemoryRouter><SegmentsClientPage /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  creditApi.getConditionsSegment.mockResolvedValue({ data: CONDITIONS })
  creditApi.getExposition.mockResolvedValue({ data: EXPOSITION })
  creditApi.getSegmentsClient.mockResolvedValue({ data: rattachement('standard') })
  creditApi.updateSegmentClient.mockResolvedValue({ data: {} })
  creditApi.createSegmentClient.mockResolvedValue({ data: { id: 6 } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SegmentsClientPage (PACT50)', () => {
  it('changer le segment d’un client fait apparaître les conditions du NOUVEAU segment', async () => {
    const user = userEvent.setup()
    creditApi.getSegmentsClient
      .mockResolvedValueOnce({ data: rattachement('standard') })
      .mockResolvedValueOnce({ data: rattachement('grand_compte') })
    monter()

    const ligne = await screen.findByTestId('segment-client-7')
    expect(within(ligne).getByText('30 j')).toBeInTheDocument()
    expect(within(ligne).getByText('40.00 %')).toBeInTheDocument()

    await user.selectOptions(
      screen.getByLabelText('Segment de Villa Zenith'), 'grand_compte')

    expect(creditApi.updateSegmentClient).toHaveBeenCalledWith(5, {
      segment: 'grand_compte',
    })
    expect(await within(await screen.findByTestId('segment-client-7'))
      .findByText('90 j')).toBeInTheDocument()
    expect(within(screen.getByTestId('segment-client-7')).getByText('10.00 %'))
      .toBeInTheDocument()
    expect(within(screen.getByTestId('segment-client-7')).getByText('avertissement'))
      .toBeInTheDocument()
  })

  it('un segment sans condition configurée est DIT, jamais rendu par un tiret muet', async () => {
    creditApi.getSegmentsClient.mockResolvedValue({ data: rattachement('exotique') })
    monter()

    const ligne = await screen.findByTestId('segment-client-7')
    expect(within(ligne).getByText('aucune condition configurée')).toBeInTheDocument()
    expect(within(ligne).getAllByText('défaut société').length).toBe(2)
  })

  it('rattache un client à un segment (le maillon qui rend les conditions applicables)', async () => {
    const user = userEvent.setup()
    creditApi.getSegmentsClient.mockResolvedValue({ data: [] })
    monter()

    await screen.findByTestId('credit-segments-client')
    await user.selectOptions(screen.getByLabelText('Client à rattacher'), '9')
    await user.selectOptions(screen.getByLabelText('Segment'), 'grand_compte')
    await user.click(screen.getByRole('button', { name: 'Rattacher' }))

    expect(creditApi.createSegmentClient).toHaveBeenCalledWith({
      client: '9', segment: 'grand_compte',
    })
  })
})
