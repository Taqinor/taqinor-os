import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTCON14 — planning tous corps d'état groupé PAR LOT : chaque lot porte son
   code couleur (serveur), ses tâches rattachées, son avancement et son badge
   de retard/jalon contractuel. Aucun calcul métier côté client. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { planningLots, lotsCreate } = vi.hoisted(() => ({
  planningLots: vi.fn(),
  lotsCreate: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    planningLots: (...args) => planningLots(...args),
    lots: { create: (...args) => lotsCreate(...args) },
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 5, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import PlanningLots, { bornesPlanning, barre } from './PlanningLots'

beforeEach(() => {
  vi.clearAllMocks()
  planningLots.mockResolvedValue({
    data: [
      {
        id: 1, nom: 'Gros-œuvre', ordre: 1, couleur: '#2563EB',
        statut: 'en_cours', jalon_contractuel: true, interne: true,
        sous_traitant_id: null, sous_traitant_nom: '',
        date_debut_prevue: '2026-01-05', date_fin_prevue: '2026-03-01',
        date_fin_reelle: null, avancement_pct: 75, en_retard: true,
        taches: [
          { id: 11, libelle: 'Fondations', statut: 'termine', avancement_pct: 100, date_debut_prevue: '2026-01-05', date_fin_prevue: '2026-02-01' },
          { id: 12, libelle: 'Élévations', statut: 'en_cours', avancement_pct: 50, date_debut_prevue: '2026-02-02', date_fin_prevue: '2026-03-01' },
        ],
      },
      {
        id: 2, nom: 'Électricité', ordre: 2, couleur: '#16A34A',
        statut: 'planifie', jalon_contractuel: false, interne: false,
        sous_traitant_id: 7, sous_traitant_nom: 'ELEC SARL',
        date_debut_prevue: '2026-03-02', date_fin_prevue: '2026-04-01',
        date_fin_reelle: null, avancement_pct: 0, en_retard: false,
        taches: [],
      },
    ],
  })
})

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

async function choisirChantier(user) {
  const select = await screen.findByLabelText('Chantier du planning')
  await user.selectOptions(
    select, within(select).getByRole('option', { name: /Villa Zenith/ }),
  )
}

describe('PlanningLots (NTCON14)', () => {
  it('groupe le Gantt par lot avec les tâches rattachées', async () => {
    const user = userEvent.setup()
    withProviders(<PlanningLots />)
    await choisirChantier(user)

    await waitFor(() => expect(planningLots).toHaveBeenCalledWith('5'))
    expect(await screen.findByText('Gros-œuvre')).toBeTruthy()
    const lot = screen.getByLabelText('Lot Gros-œuvre')
    expect(within(lot).getByText(/Fondations/)).toBeTruthy()
    expect(within(lot).getByText(/Élévations/)).toBeTruthy()
    expect(within(lot).getByText('Jalon contractuel')).toBeTruthy()
    expect(within(lot).getByText('En retard')).toBeTruthy()
    expect(within(lot).getByText('75%')).toBeTruthy()
  })

  it('affiche la couleur du lot renvoyée par le serveur', async () => {
    const user = userEvent.setup()
    withProviders(<PlanningLots />)
    await choisirChantier(user)

    const barreLot = await screen.findByTestId('btp-lot-barre-1')
    expect(barreLot.style.background).toContain('37, 99, 235')
  })

  it('affiche le sous-traitant d’un lot non interne', async () => {
    const user = userEvent.setup()
    withProviders(<PlanningLots />)
    await choisirChantier(user)

    const lot = await screen.findByLabelText('Lot Électricité')
    expect(within(lot).getByText('ELEC SARL')).toBeTruthy()
  })

  it('crée un lot sur le chantier sélectionné', async () => {
    const user = userEvent.setup()
    withProviders(<PlanningLots />)
    await choisirChantier(user)
    await screen.findByText('Gros-œuvre')

    await user.type(screen.getByLabelText('Nom du lot'), 'Plomberie')
    await user.click(screen.getByRole('button', { name: 'Ajouter le lot' }))

    await waitFor(() => expect(lotsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ chantier: '5', nom: 'Plomberie' }),
    ))
  })
})

describe('bornesPlanning / barre (NTCON14)', () => {
  it('renvoie null quand rien n’est daté', () => {
    expect(bornesPlanning([{ id: 1, taches: [] }])).toBeNull()
    expect(barre(null, '2026-01-01', '2026-02-01')).toBeNull()
  })

  it('borne la fenêtre sur les dates min/max et positionne la barre', () => {
    const bornes = bornesPlanning([
      { date_debut_prevue: '2026-01-01', date_fin_prevue: '2026-02-01', taches: [] },
      { date_debut_prevue: '2026-02-01', date_fin_prevue: '2026-04-01', taches: [] },
    ])
    expect(bornes).toEqual({ debut: '2026-01-01', fin: '2026-04-01' })
    const pos = barre(bornes, '2026-01-01', '2026-04-01')
    expect(pos.left).toBe('0%')
    expect(pos.width).toBe('100%')
  })
})
