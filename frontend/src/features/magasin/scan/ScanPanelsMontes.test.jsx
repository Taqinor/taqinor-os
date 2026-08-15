import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* WIR193 — les trois panneaux scan-first de l'entrepôt (réception XSTK5,
   prélèvement XSTK5, comptage XSTK6) étaient CONSTRUITS et TESTÉS mais montés
   NULLE PART : ils étaient inatteignables depuis l'application. Ce test garde
   le MONTAGE (l'affordance « Scan » de chaque écran hôte rend bien le
   panneau) — le comportement de scan lui-même reste couvert par les tests
   propres à chaque panneau. */

vi.mock('../../../api/installationsApi', () => ({
  default: {
    getPickLists: vi.fn(() => Promise.resolve({ data: [] })),
    getPickList: vi.fn(),
    updatePickListLigne: vi.fn(),
    demarrerPickList: vi.fn(),
    terminerPickList: vi.fn(),
    getSessionsComptage: vi.fn(() => Promise.resolve({ data: [] })),
    getSessionComptage: vi.fn(),
    ajouterLigneComptage: vi.fn(),
    updateComptageLigne: vi.fn(),
    demarrerComptage: vi.fn(),
    terminerComptage: vi.fn(),
    createSessionComptage: vi.fn(),
  },
}))
vi.mock('../../../api/stockApi', () => ({
  default: {
    getProduits: vi.fn(() => Promise.resolve({ data: [] })),
    getBonCommandeFournisseur: vi.fn(),
    getBonsCommandeFournisseur: vi.fn(() => Promise.resolve({ data: [] })),
    getReceptionsFournisseur: vi.fn(() => Promise.resolve({ data: [] })),
    getReceptionFournisseur: vi.fn(),
    createReceptionFournisseur: vi.fn(),
    confirmerReceptionFournisseur: vi.fn(),
    annulerReceptionFournisseur: vi.fn(),
    facturerReception: vi.fn(),
    receptionEtiquettes: vi.fn(),
    resolveCode: vi.fn(),
    recevoirBcf: vi.fn(),
  },
}))
vi.mock('../../parametres/useStockFlags', () => ({
  default: () => ({ stock_scan_actif: true, stock_lots_series_actif: true }),
}))

import installationsApi from '../../../api/installationsApi'
import stockApi from '../../../api/stockApi'

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

// Charge utile alignée sur `PickListSerializer` (created_by, date_creation,
// date_modification, id, installation, lignes, note, reference, statut,
// statut_display) — jamais un champ inventé.
const PICK_LIST = {
  id: 3, reference: 'PICK-001', statut: 'en_cours', statut_display: 'En cours',
  installation: 4, note: '', created_by: 1,
  date_creation: '2026-07-01', date_modification: '2026-07-01',
  lignes: [{
    id: 30, produit: 5, produit_nom: 'Panneau 550W', bin_code: 'A-01-1',
    quantite_demandee: 4, quantite_prelevee: 0, preleve: false,
  }],
}

describe('WIR193 — les panneaux scan-first sont atteignables', () => {
  it('prélèvement : « Scan » monte PickingScanPanel dans le bon ouvert', async () => {
    installationsApi.getPickLists.mockResolvedValue({ data: [PICK_LIST] })
    installationsApi.getPickList.mockResolvedValue({ data: PICK_LIST })
    const { default: PickListScreen } = await import('../PickListScreen')
    const user = userEvent.setup()
    render(<MemoryRouter><PickListScreen /></MemoryRouter>)

    await user.click(await screen.findByText('PICK-001'))
    const bouton = await screen.findByRole('button', { name: 'Scan' })
    expect(bouton).toHaveAttribute('aria-expanded', 'false')

    await user.click(bouton)
    // Le panneau charge le bon via l'API existante — preuve qu'il est monté.
    await waitFor(() => expect(installationsApi.getPickList)
      .toHaveBeenCalledWith(3))
    expect(await screen.findByRole('button', { name: 'Masquer le scan' }))
      .toBeInTheDocument()
  })

  it('comptage : « Scan » monte ComptageScanPanel sur la session ouverte', async () => {
    const session = {
      id: 9, reference: 'CYC-001', statut: 'en_cours', classe_abc: 'A',
      lignes: [], date_creation: '2026-07-01',
    }
    installationsApi.getSessionsComptage.mockResolvedValue({ data: [session] })
    const { default: ComptageCyclesScreen } = await import('../../logistique/ComptageCyclesScreen')
    const user = userEvent.setup()
    render(<MemoryRouter><ComptageCyclesScreen /></MemoryRouter>)

    // Il faut d'abord ouvrir une session : le panneau vit dans son détail.
    await user.click(await screen.findByText('CYC-001'))
    const bouton = await screen.findByRole('button', { name: 'Scan' })
    expect(bouton).toHaveAttribute('aria-expanded', 'false')

    await user.click(bouton)
    expect(await screen.findByRole('button', { name: 'Masquer le scan' }))
      .toBeInTheDocument()
  })

  it('réception : aucune affordance de scan tant qu’aucun BCF n’est choisi', async () => {
    const { default: ReceptionsFournisseur } = await import('../../../pages/stock/ReceptionsFournisseur')
    render(<MemoryRouter><ReceptionsFournisseur /></MemoryRouter>)

    // Le panneau de réception scan-first est attaché au BCF sélectionné dans
    // le modal « nouvelle réception » : rien ne doit apparaître sur la liste.
    await waitFor(() => expect(stockApi.getReceptionsFournisseur).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: 'Scan' })).toBeNull()
  })
})
