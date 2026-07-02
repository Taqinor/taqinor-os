import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'

/* WR11 / FG290 — registre des garanties par parc : totaux, parcs triés par
   échéance, statut d'alerte par unité. savApi mocké. */

vi.mock('../../api/savApi', () => ({
  default: {
    getRegistreGaranties: vi.fn(() => Promise.resolve({
      data: {
        today: '2026-07-01',
        expiring_soon_days: 60,
        totaux: {
          equipements: 3, expirees: 1, expire_bientot: 1,
          sous_garantie: 1, non_renseignee: 0,
        },
        parcs: [{
          installation: 4,
          installation_nom: 'INST-2026-0004',
          client_nom: 'Karim Alaoui',
          prochaine_echeance: '2026-07-15',
          alertes: { expirees: 1, expire_bientot: 1, sous_garantie: 1, non_renseignee: 0 },
          items: [
            {
              equipement: 11, produit: 'Onduleur X', marque: 'Huawei',
              numero_serie: 'SN-1', date_pose: '2024-07-01',
              date_fin_garantie: '2026-07-15',
              date_fin_garantie_production: null,
              statut_garantie: 'expire_bientot',
              statut_garantie_production: 'non_renseignee',
              statut: 'en_service',
            },
            {
              equipement: 12, produit: 'Panneau Y', marque: '',
              numero_serie: '', date_pose: '2020-01-01',
              date_fin_garantie: '2025-01-01',
              date_fin_garantie_production: null,
              statut_garantie: 'expiree',
              statut_garantie_production: 'non_renseignee',
              statut: 'en_service',
            },
          ],
        }],
      },
    })),
  },
}))

import savApi from '../../api/savApi'
import RegistreGarantiesDialog from './RegistreGarantiesDialog'

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RegistreGarantiesDialog (WR11 — FG290)', () => {
  it('rend les totaux, le parc et les statuts de garantie', async () => {
    render(<RegistreGarantiesDialog onClose={vi.fn()} />)
    expect(savApi.getRegistreGaranties).toHaveBeenCalled()
    await waitFor(() =>
      expect(screen.getByTestId('registre-garanties')).toBeInTheDocument())

    // Totaux
    expect(screen.getByText('3 équipement(s)')).toBeInTheDocument()
    expect(screen.getByText('1 expirée(s)')).toBeInTheDocument()
    expect(screen.getByText(/expire\(nt\) sous 60 j/)).toBeInTheDocument()

    // Parc + unités
    expect(screen.getByText('INST-2026-0004 — Karim Alaoui')).toBeInTheDocument()
    expect(screen.getByText('Onduleur X')).toBeInTheDocument()
    expect(screen.getByText('Expire bientôt')).toBeInTheDocument()
    expect(screen.getByText('Expirée')).toBeInTheDocument()
  })

  it('affiche une erreur lisible si le registre échoue', async () => {
    savApi.getRegistreGaranties.mockRejectedValueOnce(new Error('x'))
    render(<RegistreGarantiesDialog onClose={vi.fn()} />)
    await waitFor(() =>
      expect(screen.getByText(/Registre indisponible/)).toBeInTheDocument())
  })
})
