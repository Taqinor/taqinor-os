import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR8 — Paramètres → Hôtellerie : taxe de séjour (singleton société).
   `services.cloturer_folio` retombe silencieusement sur Decimal('0') tant
   qu'aucune ligne n'est configurée : cet écran est le seul chemin d'écriture
   hors admin Django. */

beforeAll(() => {
  // jsdom n'implémente pas ResizeObserver (Radix Switch).
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { getParametresTaxeSejour, saveParametresTaxeSejour } = vi.hoisted(() => ({
  getParametresTaxeSejour: vi.fn(() => Promise.resolve({
    data: { id: null, montant_par_nuit_par_personne: '0.00', exoneration_enfants: true, actif: false },
  })),
  saveParametresTaxeSejour: vi.fn((data) => Promise.resolve({
    data: { id: 1, montant_par_nuit_par_personne: '25.00', exoneration_enfants: true, actif: true, ...data },
  })),
}))

vi.mock('../../api/hospitalityApi', () => ({
  default: { getParametresTaxeSejour, saveParametresTaxeSejour },
}))

import TaxeSejourHospitality from './TaxeSejourHospitality'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('TaxeSejourHospitality (WIR8)', () => {
  it('charge les réglages courants (défaut = inactif, montant 0)', async () => {
    render(<TaxeSejourHospitality />)

    expect(await screen.findByLabelText('Montant par nuit et par personne (MAD)'))
      .toHaveValue(0)
    expect(getParametresTaxeSejour).toHaveBeenCalled()
  })

  it('un admin configure le montant et l’active — la valeur persiste', async () => {
    const user = userEvent.setup()
    render(<TaxeSejourHospitality />)

    const montant = await screen.findByLabelText('Montant par nuit et par personne (MAD)')
    await user.clear(montant)
    await user.type(montant, '25')
    await user.click(screen.getByRole('switch', { name: 'Taxe de séjour active' }))
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))

    await waitFor(() => expect(saveParametresTaxeSejour).toHaveBeenCalledWith(
      expect.objectContaining({ montant_par_nuit_par_personne: '25', actif: true }),
    ))
    expect(await screen.findByText('Enregistré')).toBeInTheDocument()
  })
})
