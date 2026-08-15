import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* WIR225 — « % de variation par défaut » des variantes de devis, réglable
   depuis Paramètres → Devis. Le réglage passe par l'endpoint dédié
   `/ventes/devis/variante-config/` (QG9) : lecture ouverte à tous les rôles,
   écriture réservée au Directeur / Commercial responsable. */

vi.mock('../../api/ventesApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getVarianteConfig: vi.fn(),
      setVarianteConfig: vi.fn(),
    },
  }
})

import ventesApi from '../../api/ventesApi'
import DevisSection from './DevisSection'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const form = {
  payment_terms: {}, quote_validity_days: 30, agricole_pump_hours: 7,
  doc_prefixes: {}, doc_numbering: {}, commission_mode: 'off',
  commission_valeur: '', tva_standard: 20, tva_panneaux: 10,
}
const noop = () => {}

function renderSection(role_nom) {
  const store = configureStore({
    reducer: { auth: (s = { role: 'admin', role_nom, permissions: [] }) => s },
  })
  return render(
    <Provider store={store}>
      <ThemeProvider>
        <DevisSection form={form} set={noop} setForm={noop} setPT={noop}
                      setPrefix={noop} setNumbering={noop}
                      numberingPreview={() => 'DEV-2026-07-0001'} />
      </ThemeProvider>
    </Provider>,
  )
}

describe('WIR225 — % de variation par défaut (paramètres devis)', () => {
  it('charge la valeur société et l’enregistre (Directeur)', async () => {
    ventesApi.getVarianteConfig.mockResolvedValue({ data: { variante_pct: '20.00' } })
    ventesApi.setVarianteConfig.mockResolvedValue({ data: { variante_pct: '15' } })
    const user = userEvent.setup()
    renderSection('Directeur')

    const champ = await screen.findByLabelText(/% de variation par défaut/)
    await waitFor(() => expect(champ).toHaveValue(20))

    await user.clear(champ)
    await user.type(champ, '15')
    await user.click(screen.getByRole('button', { name: /Enregistrer le %/ }))

    await waitFor(() => expect(ventesApi.setVarianteConfig).toHaveBeenCalledWith('15'))
  })

  it('rôle non autorisé : lecture seule, aucun bouton d’enregistrement', async () => {
    ventesApi.getVarianteConfig.mockResolvedValue({ data: { variante_pct: '20.00' } })
    renderSection('Commercial')

    const champ = await screen.findByLabelText(/% de variation par défaut/)
    await waitFor(() => expect(champ).toBeDisabled())
    expect(screen.queryByRole('button', { name: /Enregistrer le %/ })).toBeNull()
    expect(screen.getByText(/Seuls le Directeur et le Commercial responsable/))
      .toBeInTheDocument()
  })
})
