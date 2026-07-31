import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR104 — cet écran est le CONSOMMATEUR du cluster réglementaire de ventes
   (FG245, FG268-287), qui était complet côté serveur et appelé nulle part.
   Le test verrouille : un appel réel par ressource, un rendu générique des
   champs renvoyés, et le changement de ressource qui rappelle l'API. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../api/ventesApi', () => ({
  default: {
    getReglementaire: vi.fn((resource) => Promise.resolve({
      data: resource === 'dossiers-reglementaires'
        ? [{ id: 1, reference: 'DR-2026-001', operateur: 'ONEE', statut: 'depose' }]
        : [{ id: 2, reference: 'CK-2026-001', etape: 'depot', statut: 'en_cours' }],
    })),
  },
}))

import ventesApi from '../../api/ventesApi'
import DossiersReglementairesPage from './DossiersReglementairesPage'

describe('DossiersReglementairesPage (WIR104)', () => {
  it('charge la première ressource et rend ses champs', async () => {
    render(<DossiersReglementairesPage />)
    await waitFor(() => expect(ventesApi.getReglementaire)
      .toHaveBeenCalledWith('dossiers-reglementaires'))
    expect(await screen.findByText('DR-2026-001')).toBeInTheDocument()
    expect(screen.getByText('ONEE')).toBeInTheDocument()
  })

  it('rappelle l\'API en changeant de ressource', async () => {
    const user = userEvent.setup()
    render(<DossiersReglementairesPage />)
    await screen.findByText('DR-2026-001')

    await user.click(screen.getByRole('radio', { name: 'Checklists' }))
    await waitFor(() => expect(ventesApi.getReglementaire)
      .toHaveBeenCalledWith('dossiers-checklist'))
    expect(await screen.findByText('CK-2026-001')).toBeInTheDocument()
  })

  it('expose toutes les ressources du cluster', () => {
    render(<DossiersReglementairesPage />)
    for (const label of [
      'Dossiers', 'Checklists', 'Échanges opérateur', 'Subventions',
      'Régularisation 82-21', 'Recette IEC 62446', 'Courbes I-V',
      'Packs as-built', 'Attestations conformité', 'Tests PR réception',
      'Attestations RE', 'Calepinages',
    ]) {
      expect(screen.getAllByRole('radio', { name: label }).length).toBeGreaterThan(0)
    }
  })
})
