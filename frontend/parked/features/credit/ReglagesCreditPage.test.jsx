import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* WIR185/NTCRD3 — `GET/PATCH /credit/reglage/` existait SANS AUCUN ÉCRAN : la
   politique de hold restait figée sur ses défauts (jamais bloquante) et la
   seule façon de la changer était l'admin Django. L'écriture est réservée
   Directeur/Administrateur côté serveur ; l'écran reflète la même règle. */

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
  seuil_alerte_exposition_globale: '0.00',
  devise_consolidation: 'MAD',
  seuil_tolerance_depassement: '0.00',
  roles_bypass_hold: [],
}

function renderPage({ role = 'admin', role_nom = 'Directeur' } = {}) {
  const store = configureStore({
    reducer: { auth: (s = { role, role_nom }) => s },
  })
  return render(<Provider store={store}><ReglagesCreditPage /></Provider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  creditApi.getReglage.mockResolvedValue({ data: REGLAGE })
  creditApi.updateReglage.mockResolvedValue({ data: REGLAGE })
})

describe('ReglagesCreditPage (WIR185)', () => {
  it('charge les huit champs servis par le serveur', async () => {
    renderPage()
    await waitFor(() => expect(creditApi.getReglage).toHaveBeenCalled())
    expect(await screen.findByLabelText('Mode de hold par défaut')).toHaveValue('avertissement')
    expect(screen.getByLabelText(/Inclure les bons de commande/)).toBeChecked()
    expect(screen.getByLabelText(/Inclure les devis en cours/)).not.toBeChecked()
    expect(screen.getByLabelText(/Seuil d’alerte \(%/)).toHaveValue(80)
    expect(screen.getByLabelText(/exposition globale/)).toHaveValue(0)
    expect(screen.getByLabelText(/Tolérance de dépassement/)).toHaveValue(0)
    expect(screen.getByLabelText('Devise de consolidation')).toHaveValue('MAD')
    expect(screen.getByLabelText(/passer outre un blocage/)).toHaveValue('')
  })

  it('enregistre le passage en « blocage » (il persiste au rechargement)', async () => {
    creditApi.updateReglage.mockResolvedValue({
      data: { ...REGLAGE, mode_hold_defaut: 'blocage' },
    })
    renderPage()
    const select = await screen.findByLabelText('Mode de hold par défaut')
    fireEvent.change(select, { target: { value: 'blocage' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(creditApi.updateReglage).toHaveBeenCalledWith(
      expect.objectContaining({ mode_hold_defaut: 'blocage' })))
    // L'écran repart de ce que le SERVEUR a enregistré.
    expect(await screen.findByTestId('credit-reglages-succes')).toBeInTheDocument()
    expect(screen.getByLabelText('Mode de hold par défaut')).toHaveValue('blocage')
  })

  it('envoie les huit champs, la liste de rôles en tableau', async () => {
    renderPage()
    const bypass = await screen.findByLabelText(/passer outre un blocage/)
    fireEvent.change(bypass, { target: { value: 'Directeur, Commercial responsable' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(creditApi.updateReglage).toHaveBeenCalledWith({
      mode_hold_defaut: 'avertissement',
      inclure_bc_non_factures: true,
      inclure_devis_en_cours: false,
      seuil_alerte_pct: '80.00',
      seuil_alerte_exposition_globale: '0.00',
      devise_consolidation: 'MAD',
      seuil_tolerance_depassement: '0.00',
      roles_bypass_hold: ['Directeur', 'Commercial responsable'],
    }))
  })

  it('un rôle non autorisé : lecture seule, sans bouton d’enregistrement', async () => {
    renderPage({ role: 'responsable', role_nom: 'Commercial responsable' })
    await screen.findByLabelText('Mode de hold par défaut')
    expect(screen.getByTestId('credit-reglages-lecture-seule')).toBeInTheDocument()
    expect(screen.getByLabelText('Mode de hold par défaut')).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Enregistrer' })).toBeNull()
    expect(creditApi.updateReglage).not.toHaveBeenCalled()
  })

  it('un 403 serveur est affiché TEL QUEL', async () => {
    creditApi.updateReglage.mockRejectedValue({
      response: { status: 403, data: { detail: 'Réservé au Directeur.' } },
    })
    renderPage()
    await screen.findByLabelText('Mode de hold par défaut')
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(await screen.findByTestId('credit-reglages-erreur')).toHaveTextContent(
      'Réservé au Directeur.')
  })
})
