import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT79 — Lots de récolte (NTAGR15/NTAGR16). Le client agricole câblait ses
   11 autres ressources et n'avait AUCUNE entrée pour celle-ci. Deux points
   structurants prouvés ici : le numéro de lot n'est jamais saisi (généré côté
   serveur, anti-collision), et un lot rattaché à un lot d'entrepôt se retrouve
   par sa traçabilité stock — un lot sans rattachement s'arrête proprement à
   l'amont, sans erreur. */

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { get, post } }))

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(), toastError: vi.fn(),
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: toastSuccess, error: toastError },
}))

import LotsRecolte from './LotsRecolte'

const CAMPAGNES = [
  { id: 4, culture: 'Blé tendre', variete: 'Achtar', date_semis: '2025-11-15' },
]
const LOTS = [
  {
    id: 31, campagne: 4, date_recolte: '2026-06-12', quantite_qtl: '145.00',
    calibre: 'A', qualite: 'Extra', numero_lot: 'LR-2026-06-0001',
    stock_lot_id: 'LOT-BLE-2026-06',
  },
  {
    id: 32, campagne: 4, date_recolte: '2026-06-20', quantite_qtl: '80.00',
    calibre: '', qualite: '', numero_lot: 'LR-2026-06-0002', stock_lot_id: '',
  },
]
const TRACE = {
  lot_id: 31, numero_lot: 'LR-2026-06-0001',
  amont: {
    parcelle_id: 2, parcelle_nom: 'Parcelle Nord', culture: 'Blé tendre',
    traitements: [{ date: '2026-03-01', produit_nom: 'Fongicide X' }],
  },
  aval: { receptions: [] },
}

function mockGets(lots = LOTS) {
  get.mockImplementation((url) => {
    if (url === '/agriculture/lots-recolte/') return Promise.resolve({ data: lots })
    if (url === '/agriculture/campagnes/') return Promise.resolve({ data: CAMPAGNES })
    if (url === '/agriculture/lots-recolte/31/tracabilite/') {
      return Promise.resolve({ data: TRACE })
    }
    if (url === '/agriculture/lots-recolte/32/tracabilite/') {
      return Promise.resolve({ data: { ...TRACE, lot_id: 32, numero_lot: 'LR-2026-06-0002', aval: null } })
    }
    return Promise.reject(new Error(`URL inattendue : ${url}`))
  })
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('LotsRecolte (PACT79)', () => {
  it('liste les lots avec quantité, calibre, qualité et rattachement stock', async () => {
    mockGets()
    render(<LotsRecolte />)

    const lot = await screen.findByTestId('lot-31')
    expect(within(lot).getByText('LR-2026-06-0001')).toBeInTheDocument()
    expect(within(lot).getByText('145.00 qx')).toBeInTheDocument()
    expect(within(lot).getByText('Calibre A')).toBeInTheDocument()
    expect(within(lot).getByText('Qualité Extra')).toBeInTheDocument()
    expect(within(lot).getByText(/Lot d'entrepôt LOT-BLE-2026-06/)).toBeInTheDocument()

    // Un lot sans rattachement stock est affiché comme tel, sans erreur.
    const sansStock = screen.getByTestId('lot-32')
    expect(within(sansStock).getByText("Sans lot d'entrepôt")).toBeInTheDocument()
  })

  it('crée un lot pour une campagne sans jamais saisir le numéro de lot', async () => {
    const user = userEvent.setup()
    mockGets()
    post.mockResolvedValue({ data: { id: 33, numero_lot: 'LR-2026-06-0003' } })
    render(<LotsRecolte />)
    await screen.findByTestId('lot-31')

    await user.click(screen.getByRole('combobox', { name: 'Campagne' }))
    await user.click(await screen.findByRole('option', { name: /Blé tendre/ }))
    fireEvent.change(screen.getByLabelText('Date de récolte'),
      { target: { value: '2026-06-25' } })
    await user.type(screen.getByLabelText('Quantité en quintaux'), '60')
    await user.click(screen.getByRole('button', { name: /Enregistrer le lot/ }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/agriculture/lots-recolte/', {
      campagne: 4, date_recolte: '2026-06-25', quantite_qtl: '60',
      calibre: '', qualite: '', stock_lot_id: '',
    }))
    // Le numéro est renvoyé par le serveur, jamais envoyé par le client.
    const corps = post.mock.calls[0][1]
    expect(Object.keys(corps)).not.toContain('numero_lot')
    expect(Object.keys(corps)).not.toContain('company')
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Lot LR-2026-06-0003 créé.'))
  })

  it('retrouve un lot depuis son lot d\'entrepôt et affiche sa traçabilité', async () => {
    const user = userEvent.setup()
    mockGets()
    render(<LotsRecolte />)
    await screen.findByTestId('lot-31')

    // Recherche par le numéro de lot d'entrepôt : c'est le chemin « depuis la
    // traçabilité stock ».
    await user.type(screen.getByLabelText('Rechercher un lot'), 'LOT-BLE')
    await waitFor(() => expect(screen.queryByTestId('lot-32')).toBeNull())

    await user.click(within(screen.getByTestId('lot-31'))
      .getByRole('button', { name: 'Traçabilité' }))

    const bloc = await screen.findByTestId('tracabilite-lot')
    expect(bloc).toHaveTextContent('LR-2026-06-0001')
    expect(bloc).toHaveTextContent('Parcelle Nord')
    expect(bloc).toHaveTextContent('1 traitement(s)')
    expect(bloc).toHaveTextContent(/chaîne stock est remontée/)
  })

  it("dit clairement qu'un lot sans rattachement s'arrête à l'amont", async () => {
    const user = userEvent.setup()
    mockGets()
    render(<LotsRecolte />)
    await screen.findByTestId('lot-32')

    await user.click(within(screen.getByTestId('lot-32'))
      .getByRole('button', { name: 'Traçabilité' }))

    const bloc = await screen.findByTestId('tracabilite-lot')
    expect(bloc).toHaveTextContent(/s'arrête à l'amont/)
  })

  it('affiche une erreur de chargement sans planter', async () => {
    get.mockImplementation((url) => {
      if (url === '/agriculture/lots-recolte/') return Promise.reject(new Error('boom'))
      return Promise.resolve({ data: [] })
    })
    render(<LotsRecolte />)
    expect(await screen.findByText('Impossible de charger les lots de récolte'))
      .toBeInTheDocument()
  })
})
