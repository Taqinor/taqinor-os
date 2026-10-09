import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// ASAV51 — « Corriger » un équipement dont le produit (102e) et le chantier
// (60e) sont au-delà de la page 1 : les sélecteurs doivent les montrer.
// Faux serveur paginé à 50 (comme DRF), count = total.

const paginer = (total, nom) => (params = {}) => {
  const page = Number(params.page ?? 1)
  const debut = (page - 1) * 50
  const results = []
  for (let i = debut + 1; i <= Math.min(total, debut + 50); i += 1) {
    results.push(nom(i))
  }
  return Promise.resolve({ data: { count: total, next: null, results } })
}

vi.mock('../../api/stockApi', () => ({
  default: { getProduits: (p) => paginer(102, (i) => ({ id: i, nom: `Produit ${i}` }))(p) },
}))
vi.mock('../../api/installationsApi', () => ({
  default: { getInstallations: (p) => paginer(60, (i) => ({ id: i, reference: `CHT-${i}` }))(p) },
}))
vi.mock('../../api/savApi', () => ({
  default: new Proxy({}, { get: () => () => Promise.resolve({ data: [] }) }),
}))
vi.mock('../../api/importApi', () => ({ default: {} }))

import { EquipementDetail } from './EquipementsPage'

describe('EquipementDetail — ASAV51 « Corriger » avec catalogue complet', () => {
  it('produit actuel (102e) et chantier actuel (60e) préremplis', async () => {
    const user = userEvent.setup()
    const store = configureStore({ reducer: { auth: (s = { role: 'admin', permissions: [] }) => s } })
    render(<Provider store={store}><MemoryRouter>
      <EquipementDetail
        equipement={{ id: 9, produit: 102, produit_nom: 'Produit 102', installation: 60,
          installation_reference: 'CHT-60', numero_serie: 'S', statut: 'en_service',
          nb_tickets_ouverts: 0 }}
        onClose={() => {}} onSaved={() => {}} />
    </MemoryRouter></Provider>)
    await user.click(screen.getByRole('button', { name: /^Corriger$/ }))
    const boites = await screen.findAllByRole('combobox')
    const texte = () => boites.map((b) => b.textContent).join('|')
    await vi.waitFor(() => {
      expect(texte()).toContain('Produit 102')
      expect(texte()).toContain('CHT-60')
    })
  }, 60000)
})
