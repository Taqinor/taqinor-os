import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT48 — Assurance-crédit : polices et encours garantis.

   Les charges utiles reprennent les champs RÉELS des sérialiseurs serveur
   (`PoliceAssuranceCreditSerializer`, `EncoursGarantiClientSerializer`) et du
   dictionnaire d'exposition (`selectors.rapport_exposition`, servi par
   `views.exposition_credit` sous `{count, resultats}`), jamais une forme
   inventée : `scripts/check_api_shapes.py` compare ces mocks au code serveur.
   Le point vérifié est celui du contrat : `garantie_assurance: null` — un
   client sans encours garanti ACCORDÉ — doit s'afficher « Non couvert », pas
   un tiret ni un zéro. */

vi.mock('../../api/creditApi', () => ({
  default: {
    getPolicesAssurance: vi.fn(),
    getEncoursGarantis: vi.fn(),
    getExposition: vi.fn(),
    createPoliceAssurance: vi.fn(),
    createEncoursGaranti: vi.fn(),
  },
}))

import creditApi from '../../api/creditApi'
import PolicesAssuranceCreditPage from './PolicesAssuranceCreditPage'

const jourISO = (decalage) =>
  new Date(Date.now() + decalage * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)

const POLICES = [
  {
    id: 1, assureur: 'Coface', numero_police: 'MA-2026-77',
    date_debut: '2026-01-01', date_fin: jourISO(10), franchise: '5000.00',
    taux_couverture_pct: '90.00', plafond_global: '2000000.00', actif: true,
    date_creation: '2026-01-01T09:00:00Z', date_modification: '2026-01-01T09:00:00Z',
  },
  {
    id: 2, assureur: 'Atradius', numero_police: '', date_debut: '2024-01-01',
    date_fin: '2025-01-01', franchise: null, taux_couverture_pct: null,
    plafond_global: null, actif: false,
    date_creation: '2024-01-01T09:00:00Z', date_modification: '2024-01-01T09:00:00Z',
  },
]

const ENCOURS = [
  {
    id: 8, police: 1, client: 7, montant_garanti: '300000.00',
    date_agrement: '2026-02-15', statut_agrement: 'accorde',
    reference_assureur: 'AGR-991', date_creation: '2026-02-15T10:00:00Z',
  },
]

const EXPOSITION = {
  count: 2,
  resultats: [
    {
      client_id: 7, client_nom: 'Villa Zenith', encours: '120000.00',
      limite: '400000.00', disponible: '280000.00', pct_utilise: 0.3,
      depasse: false, lettre_score: 'B', mode_hold: 'avertissement',
      garantie_assurance: '300000.00', depasse_garantie: false,
    },
    {
      client_id: 9, client_nom: 'Ferme Tadla', encours: '50000.00',
      limite: null, disponible: null, pct_utilise: null, depasse: false,
      lettre_score: 'A', mode_hold: null,
      garantie_assurance: null, depasse_garantie: false,
    },
  ],
}

function monterMocks() {
  creditApi.getPolicesAssurance.mockResolvedValue({ data: POLICES })
  creditApi.getEncoursGarantis.mockResolvedValue({ data: ENCOURS })
  creditApi.getExposition.mockResolvedValue({ data: EXPOSITION })
  creditApi.createEncoursGaranti.mockResolvedValue({ data: { id: 9 } })
  creditApi.createPoliceAssurance.mockResolvedValue({ data: { id: 3 } })
}

beforeEach(() => { vi.clearAllMocks(); monterMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PolicesAssuranceCreditPage (PACT48)', () => {
  it('un client sans encours garanti déclaré est dit « Non couvert » (jamais supposé)', async () => {
    render(<PolicesAssuranceCreditPage />)

    const bloc = await screen.findByTestId('credit-assurance-couverture')
    const ligneNonCouverte = within(bloc).getByText('Ferme Tadla').closest('tr')
    expect(within(ligneNonCouverte).getByText('Non couvert')).toBeInTheDocument()

    // Le client réellement garanti montre SON montant, pas un état.
    const ligneCouverte = within(bloc).getByText('Villa Zenith').closest('tr')
    expect(within(ligneCouverte).queryByText('Non couvert')).not.toBeInTheDocument()
    expect(within(bloc).getByText(/1 client\(s\) sans encours garanti déclaré/))
      .toBeInTheDocument()
  })

  it('liste les polices avec leur alerte d’échéance (proche / expirée)', async () => {
    render(<PolicesAssuranceCreditPage />)

    const bloc = await screen.findByTestId('credit-assurance-polices')
    const coface = within(bloc).getByText('Coface').closest('tr')
    expect(within(coface).getByText(/Échéance proche/)).toBeInTheDocument()
    expect(within(coface).getByText('90.00 %')).toBeInTheDocument()

    const atradius = within(bloc).getByText('Atradius').closest('tr')
    expect(within(atradius).getByText('Expirée')).toBeInTheDocument()
    expect(within(atradius).getByText('Inactive')).toBeInTheDocument()
  })

  it('déclare un encours garanti pour un client sur une police', async () => {
    const user = userEvent.setup()
    render(<PolicesAssuranceCreditPage />)
    await screen.findByTestId('credit-assurance-encours')

    await user.selectOptions(screen.getByLabelText('Police'), '1')
    await user.selectOptions(screen.getByLabelText('Client'), '9')
    await user.type(screen.getByLabelText('Montant garanti'), '150000')
    await user.selectOptions(screen.getByLabelText('Statut d’agrément'), 'accorde')
    await user.click(screen.getByRole('button', { name: /Déclarer l’encours garanti/ }))

    expect(creditApi.createEncoursGaranti).toHaveBeenCalledWith({
      police: '1',
      client: '9',
      montant_garanti: '150000',
      statut_agrement: 'accorde',
      date_agrement: null,
      reference_assureur: '',
    })
  })
})
