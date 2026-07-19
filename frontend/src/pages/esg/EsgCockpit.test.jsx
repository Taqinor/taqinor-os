import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const PERIODES = [
  { id: 1, libelle: 'Exercice 2025', date_debut: '2025-01-01', date_fin: '2025-12-31', statut: 'brouillon' },
  { id: 2, libelle: 'Exercice 2026', date_debut: '2026-01-01', date_fin: '2026-12-31', statut: 'brouillon' },
]

vi.mock('../../api/esgApi', () => ({
  default: {
    catalogue: {
      couverture: vi.fn(() => Promise.resolve({ data: { piliers: {} } })),
      badgeMaturite: vi.fn(() => Promise.resolve({ data: null })),
    },
    periodes: {
      list: vi.fn(() => Promise.resolve({ data: PERIODES })),
      create: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
      comparer: vi.fn(() => Promise.resolve({ data: {
        periode_reference: { id: 1, libelle: 'Exercice 2025' },
        periode_n: { id: 2, libelle: 'Exercice 2026' },
        piliers: {
          environnement: [
            { code: 'co2', libelle: 'Émissions CO2', comparable: true, valeur_reference: 100, valeur_n: 90, variation_abs: -10, variation_pct: -10 },
          ],
        },
      } })),
      dpef: vi.fn(() => Promise.resolve({ data: new Blob(['# DPEF']) })),
    },
  },
}))
vi.mock('../../api/importApi', () => ({ downloadXlsx: vi.fn() }))
vi.mock('../../utils/downloadBlob', () => ({ downloadBlob: vi.fn() }))

import esgApi from '../../api/esgApi'
import { downloadBlob } from '../../utils/downloadBlob'
import EsgCockpit from './EsgCockpit'

describe('EsgCockpit (WIR129)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('crée une période depuis le dialogue', async () => {
    render(<EsgCockpit />)
    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle période/ }))
    fireEvent.change(await screen.findByLabelText('Libellé'), { target: { value: 'Exercice 2027' } })
    fireEvent.change(screen.getByLabelText('Date de début'), { target: { value: '2027-01-01' } })
    fireEvent.change(screen.getByLabelText('Date de fin'), { target: { value: '2027-12-31' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(esgApi.periodes.create).toHaveBeenCalledWith({
      libelle: 'Exercice 2027', date_debut: '2027-01-01', date_fin: '2027-12-31',
    }))
  })

  it('compare deux périodes et affiche les écarts', async () => {
    render(<EsgCockpit />)
    await screen.findByText('Comparer deux périodes')
    fireEvent.change(screen.getByLabelText('Période (N)'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Référence (N-1)'), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Comparer' }))
    await waitFor(() => expect(esgApi.periodes.comparer).toHaveBeenCalledWith('2', '1'))
    expect(await screen.findByText('Émissions CO2')).toBeInTheDocument()
  })

  it('télécharge le DPEF d\'une période', async () => {
    render(<EsgCockpit />)
    const dpefButtons = await screen.findAllByRole('button', { name: /DPEF/ })
    fireEvent.click(dpefButtons[0])
    await waitFor(() => expect(esgApi.periodes.dpef).toHaveBeenCalled())
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled())
  })
})
