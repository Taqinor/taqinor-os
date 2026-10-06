// CIQ226 — la facture affiche sa retenue de garantie et son montant EXIGIBLE ;
// « Libérer la retenue » appelle l'action serveur (CIQ214) à la date saisie
// et rafraîchit le montant exigible avec la réponse. Référence de commande
// du client éditable et renvoyée.
// Run : npx vitest run src/pages/ventes/FactureFormRetenue.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

const apis = vi.hoisted(() => ({
  ventes: {
    libererRetenueFacture: vi.fn(),
    getBonsCommande: vi.fn(() => Promise.resolve({ data: [] })),
    getFacture: vi.fn(() => Promise.resolve({ data: {} })),
  },
  crm: { getClients: vi.fn(() => Promise.resolve({ data: [] })) },
  stock: { getProduits: vi.fn(() => Promise.resolve({ data: { results: [], next: null } })) },
}))
vi.mock('../../api/ventesApi', () => ({ default: apis.ventes }))
vi.mock('../../api/crmApi', () => ({ default: apis.crm }))
vi.mock('../../api/stockApi', () => ({ default: apis.stock }))

import ventesReducer from '../../features/ventes/store/ventesSlice'
import authReducer from '../../features/auth/store/authSlice'
import FactureForm from './FactureForm'

const FACTURE = {
  id: 77, reference: 'FAC-202610-0001', client: 9, statut: 'emise', taux_tva: '20.00',
  remise_globale: '0', lignes: [], reference_commande_client: 'BC-2026-0457',
  retenue_garantie_mad: '5000.00', retenue_liberee_le: null,
  montant_du: '100000.00', montant_exigible: '95000.00', updated_at: '2026-10-01T10:00:00Z',
}

function rendre() {
  const store = configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: { auth: { user: { id: 1 }, role: 'responsable', permissions: [], isAuthenticated: true, loading: false } },
  })
  return render(
    <Provider store={store}>
      <FactureForm facture={FACTURE} onClose={() => {}} onSaved={() => {}} />
    </Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('CIQ226 — FactureForm : retenue de garantie', () => {
  it('« Libérer la retenue » appelle l’action à la date saisie et rafraîchit le montant exigible', async () => {
    apis.ventes.libererRetenueFacture.mockResolvedValue({
      data: { ...FACTURE, retenue_liberee_le: '2026-12-15', montant_exigible: '100000.00' },
    })
    rendre()
    expect(screen.getByTestId('fc-retenue')).toHaveTextContent('non libérée')
    expect(screen.getByTestId('fc-liberer-retenue')).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Date de réception définitive'), { target: { value: '2026-12-15' } })
    fireEvent.click(screen.getByTestId('fc-liberer-retenue'))
    expect(await screen.findByText(/libérée le 2026-12-15/)).toBeInTheDocument()
    expect(apis.ventes.libererRetenueFacture).toHaveBeenCalledWith(77, '2026-12-15')
    expect(screen.getByTestId('fc-montant-exigible')).toHaveTextContent('100')
  })

  it('la référence de commande du client est affichée et éditable', () => {
    rendre()
    expect(screen.getByLabelText('Référence de commande du client')).toHaveValue('BC-2026-0457')
  })
})
