import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'

/* NTCRM25 — widget dashboard Directeur « zones non couvertes ». axios mocké. */

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({
      data: {
        total_non_couverts: 1,
        leads: [{ lead_id: 7, nom: 'Lead Errachidia', ville: 'Errachidia', type_installation: 'residentiel' }],
        par_region: { Errachidia: 1 },
        par_segment: { residentiel: 1 },
      },
    })),
  },
}))

import api from '../../api/axios'
import TerritoryCoverageWidget from './TerritoryCoverageWidget'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(<TerritoryCoverageWidget />)
}

describe('TerritoryCoverageWidget (NTCRM25)', () => {
  it('liste les régions non couvertes réelles', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Errachidia')).toBeInTheDocument())
    expect(screen.getByText('1 lead non couvert')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/territoires/couverture/', { params: { jours: 30 } })
  })

  it('affiche un état vide quand la couverture est saine', async () => {
    api.get.mockResolvedValueOnce({ data: { total_non_couverts: 0, leads: [], par_region: {}, par_segment: {} } })
    mount()
    await waitFor(() => expect(screen.getByText(/Toute la couverture est saine/)).toBeInTheDocument())
  })

  it('affiche un message d\'indisponibilité en cas d\'erreur', async () => {
    api.get.mockRejectedValueOnce(new Error('boom'))
    mount()
    await waitFor(() => expect(screen.getByText(/Indisponible pour le moment/)).toBeInTheDocument())
  })
})
