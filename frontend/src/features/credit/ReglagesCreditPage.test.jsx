import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* WIR185/NTCRD3 — Réglages crédit société.

   Charge utile alignée sur `ReglageCreditSerializer` (les 8 champs éditables
   + id/dates), jamais une forme inventée. Le critère : le mode de hold choisi
   part réellement au serveur et l'écran repart de la réponse — c'est ce qui
   fait qu'il « persiste après rechargement ». Les rôles hors
   Directeur/Administrateur voient l'écran en LECTURE SEULE. */

vi.mock('../../api/creditApi', () => ({
  default: {
    getReglage: vi.fn(),
    updateReglage: vi.fn(),
  },
}))

import creditApi from '../../api/creditApi'
import ReglagesCreditPage from './ReglagesCreditPage'

const REGLAGE = {
  id: 1,
  mode_hold_defaut: 'avertissement',
  inclure_bc_non_factures: true,
  inclure_devis_en_cours: false,
  seuil_alerte_pct: '80.00',
  seuil_alerte_exposition_globale: '1000000.00',
  devise_consolidation: 'MAD',
  seuil_tolerance_depassement: '500.00',
  roles_bypass_hold: ['Directeur'],
  date_creation: '2026-01-01T09:00:00Z',
  date_modification: '2026-01-01T09:00:00Z',
}

function renderPage(role = 'admin', role_nom = 'Administrateur') {
  const store = configureStore({
    reducer: { auth: (s = { role, role_nom, permissions: [] }) => s },
  })
  return render(
    <Provider store={store}><ReglagesCreditPage /></Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('ReglagesCreditPage (WIR185)', () => {
  it('charge les réglages de la société dans le formulaire', async () => {
    creditApi.getReglage.mockResolvedValue({ data: REGLAGE })
    renderPage()

    expect(await screen.findByLabelText(/Mode de hold par défaut/))
      .toHaveValue('avertissement')
    expect(screen.getByLabelText(/Seuil d'alerte \(% de la limite\)/)).toHaveValue(80)
    expect(screen.getByLabelText(/Devise de consolidation/)).toHaveValue('MAD')
    // La liste JSON est présentée en texte séparé par des virgules.
    expect(screen.getByLabelText(/Rôles autorisés à passer outre/)).toHaveValue('Directeur')
    expect(screen.getByLabelText(/bons de commande non facturés/)).toBeChecked()
    expect(screen.getByLabelText(/devis en cours/)).not.toBeChecked()
  })

  it('enregistre mode_hold_defaut=blocage et repart de la réponse serveur', async () => {
    creditApi.getReglage.mockResolvedValue({ data: REGLAGE })
    creditApi.updateReglage.mockResolvedValue({
      data: { ...REGLAGE, mode_hold_defaut: 'blocage' },
    })
    const user = userEvent.setup()
    renderPage()

    const select = await screen.findByLabelText(/Mode de hold par défaut/)
    await user.selectOptions(select, 'blocage')
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))

    await waitFor(() => expect(creditApi.updateReglage).toHaveBeenCalledTimes(1))
    const envoye = creditApi.updateReglage.mock.calls[0][0]
    expect(envoye.mode_hold_defaut).toBe('blocage')
    // `roles_bypass_hold` repart TOUJOURS en tableau, jamais en texte.
    expect(envoye.roles_bypass_hold).toEqual(['Directeur'])

    expect(await screen.findByRole('status')).toHaveTextContent(/enregistrés/i)
    expect(screen.getByLabelText(/Mode de hold par défaut/)).toHaveValue('blocage')
  })

  it('rôle non autorisé : lecture seule, aucun bouton d’enregistrement', async () => {
    creditApi.getReglage.mockResolvedValue({ data: REGLAGE })
    renderPage('normal', 'Commercial')

    expect(await screen.findByText(/Lecture seule/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Enregistrer/ })).toBeNull()
    expect(screen.getByLabelText(/Mode de hold par défaut/)).toBeDisabled()
  })

  it('un 403 serveur est rendu en français, jamais du JSON brut', async () => {
    creditApi.getReglage.mockResolvedValue({ data: REGLAGE })
    creditApi.updateReglage.mockRejectedValue({
      response: { status: 403, data: { detail: 'Vous n’avez pas la permission.' } },
    })
    const user = userEvent.setup()
    renderPage()

    await screen.findByLabelText(/Mode de hold par défaut/)
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText(/\{"detail"/)).toBeNull()
  })
})
