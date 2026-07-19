import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR116 — bouton « Imprimer étiquettes QR » du parc SAV. Vérifie qu'il appelle
   l'action `etiquettes` avec les ids du parc filtré et le mode public (lien
   /e/<token>), et ouvre le HTML dans un nouvel onglet. */

const items = [
  { id: 11, numero_serie: 'SN-11', produit: 1, produit_nom: 'Onduleur', garantie_etat: 'sous_garantie', date_fin_garantie: '2030-01-01', statut: 'en_service' },
  { id: 12, numero_serie: 'SN-12', produit: 1, produit_nom: 'Onduleur', garantie_etat: 'hors_garantie', date_fin_garantie: '2020-01-01', statut: 'en_service' },
]

vi.mock('react-redux', () => ({
  useDispatch: () => vi.fn(),
  useSelector: (sel) => sel({ equipements: { items, loading: false, error: null } }),
}))
vi.mock('../../features/sav/store/equipementsSlice', () => ({
  fetchEquipements: () => ({ type: 'equipements/fetch' }),
}))

const etiquettesEquipements = vi.fn(() => Promise.resolve({ data: '<html>labels</html>' }))
vi.mock('../../api/savApi', () => ({
  default: { etiquettesEquipements: (...a) => etiquettesEquipements(...a), getTickets: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/installationsApi', () => ({ default: { getInstallations: vi.fn() } }))
vi.mock('../../api/stockApi', () => ({ default: { getProduits: vi.fn() } }))
vi.mock('../../api/importApi', () => ({ default: { exportList: vi.fn(() => Promise.resolve({ data: new Blob() })) } }))
vi.mock('./RegistreGarantiesDialog', () => ({ default: () => null }))
vi.mock('./EquipementFiabilitePanel', () => ({ default: () => null }))
vi.mock('../../components/ExcelImport', () => ({ default: () => null }))

import EquipementsPage from './EquipementsPage'

beforeEach(() => {
  vi.clearAllMocks()
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:labels')
  globalThis.URL.revokeObjectURL = vi.fn()
  vi.spyOn(window, 'open').mockReturnValue({ closed: false, location: '', close: vi.fn() })
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('WIR116 — étiquettes QR équipement', () => {
  it('appelle l\'action etiquettes avec les ids du parc et le mode public', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><ThemeProvider><EquipementsPage /></ThemeProvider></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /Imprimer étiquettes QR/ }))

    await waitFor(() => expect(etiquettesEquipements).toHaveBeenCalledWith(
      expect.arrayContaining([11, 12]), { public: true },
    ))
    expect(etiquettesEquipements.mock.calls[0][0]).toHaveLength(2)
    expect(window.open).toHaveBeenCalled()
  })
})
