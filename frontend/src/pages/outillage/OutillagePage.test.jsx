import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR28 (FG80) — le backend calcule déjà `a_calibrer`/`date_prochaine_calibration`
   et expose l'action `outils/{id}/calibrer/`, mais `OutillagePage.jsx` n'en
   affichait rien : ni badge « à calibrer », ni bouton pour enregistrer une
   calibration. Réseau mocké (client API), aucune dépendance à un backend réel. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const OUTIL_A_CALIBRER = {
  id: 1, nom: 'Multimètre Fluke', categorie: 'Mesure', asset_tag: 'OUT-001',
  numero_serie: 'SN-123', emplacement: null, emplacement_nom: null,
  statut: 'disponible', date_achat: null, note: '',
  intervalle_calibration_mois: 12,
  date_derniere_calibration: '2025-01-01',
  date_prochaine_calibration: '2025-02-01',
  a_calibrer: true,
}
const OUTIL_NON_SUIVI = {
  id: 2, nom: 'Perceuse Bosch', categorie: 'Électroportatif', asset_tag: 'OUT-002',
  numero_serie: 'SN-456', emplacement: null, emplacement_nom: null,
  statut: 'disponible', date_achat: null, note: '',
  intervalle_calibration_mois: 0,
  date_derniere_calibration: null, date_prochaine_calibration: null,
  a_calibrer: false,
}

const { calibrer } = vi.hoisted(() => ({
  // Résolution par défaut sans intérêt — chaque test surcharge via
  // `mockResolvedValueOnce` avant d'agir.
  calibrer: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/outillageApi', () => ({
  default: {
    getOutils: () => Promise.resolve({ data: [OUTIL_A_CALIBRER, OUTIL_NON_SUIVI] }),
    getOutil: () => Promise.resolve({ data: OUTIL_A_CALIBRER }),
    createOutil: () => Promise.resolve({ data: {} }),
    updateOutil: () => Promise.resolve({ data: {} }),
    deleteOutil: () => Promise.resolve({ data: {} }),
    calibrer: (...args) => calibrer(...args),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { getEmplacements: () => Promise.resolve({ data: [] }) },
}))

import OutillagePage from './OutillagePage'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('OutillagePage — calibration (WIR28/FG80)', () => {
  it('affiche le badge « À calibrer » pour un outil en retard, jamais pour un outil non suivi', async () => {
    withProviders(<OutillagePage />)
    await waitFor(() => expect(screen.getByText('Multimètre Fluke')).toBeInTheDocument())

    expect(screen.getByText('À calibrer')).toBeInTheDocument()
    expect(screen.getByText('Perceuse Bosch')).toBeInTheDocument()
    // Un seul outil (Fluke) est suivi/en retard : un seul bouton de calibration.
    expect(screen.getAllByRole('button', { name: 'Enregistrer une calibration' })).toHaveLength(1)
  })

  it('enregistrer une calibration appelle l’API et recalcule l’échéance affichée', async () => {
    calibrer.mockResolvedValueOnce({
      data: { ...OUTIL_A_CALIBRER, a_calibrer: false, date_prochaine_calibration: '2027-01-15' },
    })
    const user = userEvent.setup()
    withProviders(<OutillagePage />)
    await waitFor(() => expect(screen.getByText('Multimètre Fluke')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Enregistrer une calibration' }))

    await waitFor(() => expect(calibrer).toHaveBeenCalledWith(1))
    // La calibration recalculée (a_calibrer=false) retire le badge de la ligne.
    await waitFor(() => expect(screen.queryByText('À calibrer')).not.toBeInTheDocument())
  })
})
