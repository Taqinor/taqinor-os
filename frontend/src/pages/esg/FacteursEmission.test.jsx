import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../api/esgApi', () => ({
  default: {
    facteurs: {
      list: vi.fn(() => Promise.resolve({ data: [
        { id: 1, categorie: 'Électricité', unite: 'kWh', valeur: '0.7', source: 'ADEME', version: 2, actif: true },
      ] })),
      create: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
      historique: vi.fn(() => Promise.resolve({ data: [
        { id: 1, version: 2, valeur: '0.7', source: 'ADEME', actif: true, date_maj: '2026-01-01T00:00:00Z' },
        { id: 3, version: 1, valeur: '0.8', source: 'ADEME', actif: false, date_maj: '2025-01-01T00:00:00Z' },
      ] })),
    },
  },
}))

import esgApi from '../../api/esgApi'
import FacteursEmission from './FacteursEmission'

describe('FacteursEmission (WIR130)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('liste les facteurs actifs', async () => {
    render(<FacteursEmission />)
    expect(await screen.findByText('Électricité')).toBeInTheDocument()
    expect(screen.getByText('v2')).toBeInTheDocument()
  })

  it('crée une nouvelle version de facteur', async () => {
    render(<FacteursEmission />)
    await screen.findByText('Électricité')
    fireEvent.change(screen.getByLabelText('Catégorie'), { target: { value: 'Gaz' } })
    fireEvent.change(screen.getByLabelText('Unité'), { target: { value: 'm3' } })
    fireEvent.change(screen.getByLabelText('Valeur (kgCO2e)'), { target: { value: '2.1' } })
    fireEvent.change(screen.getByLabelText('Date de mise à jour'), { target: { value: '2026-07-19T10:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(esgApi.facteurs.create).toHaveBeenCalledWith({
      categorie: 'Gaz', unite: 'm3', valeur: '2.1', source: '', date_maj: '2026-07-19T10:00',
    }))
  })

  it('affiche l\'historique de version d\'un facteur', async () => {
    render(<FacteursEmission />)
    fireEvent.click(await screen.findByRole('button', { name: /Historique/ }))
    await waitFor(() => expect(esgApi.facteurs.historique).toHaveBeenCalledWith('Électricité', 'kWh'))
    expect(await screen.findByText('v1')).toBeInTheDocument()
  })
})
