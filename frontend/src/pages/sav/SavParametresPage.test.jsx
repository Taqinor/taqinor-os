import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* ZSAV2/ZMFG1/ZMFG2/XSAV14/XSAV23 — Paramètres SAV : référentiels édités
   par responsable/admin. savApi mocké. */

vi.mock('../../api/savApi', () => ({
  default: {
    getCategoriesTicket: vi.fn(() => Promise.resolve({ data: [] })),
    saveCategorieTicket: vi.fn(),
    getCausesDefaillance: vi.fn(() => Promise.resolve({ data: [] })),
    saveCauseDefaillance: vi.fn(),
    getRemedesDefaillance: vi.fn(() => Promise.resolve({ data: [] })),
    saveRemedeDefaillance: vi.fn(),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    saveReponseType: vi.fn(),
    getEquipesMaintenance: vi.fn(() => Promise.resolve({ data: [] })),
    saveEquipeMaintenance: vi.fn(),
    getCategoriesEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    saveCategorieEquipement: vi.fn(),
  },
}))

// WIR30 — onglet SLA/Automatisation : GET/POST /sav/sla-settings/ (api axios
// direct, hors savApi — cf. SlaAutomationSection dans SavParametresPage.jsx).
vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import savApi from '../../api/savApi'
import api from '../../api/axios'
import SavParametresPage from './SavParametresPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SavParametresPage', () => {
  it('affiche l\'onglet Catégories de ticket par défaut et ajoute une catégorie', async () => {
    savApi.saveCategorieTicket.mockResolvedValue({ data: {} })
    render(<SavParametresPage />)
    await screen.findByText('Aucune catégorie')
    fireEvent.change(screen.getByPlaceholderText('Nouveau catégorie…'), { target: { value: 'Onduleur' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))
    await waitFor(() => expect(savApi.saveCategorieTicket).toHaveBeenCalledWith(
      null, { libelle: 'Onduleur' }))
  })

  it('bascule vers l\'onglet Réponses types et crée une macro', async () => {
    savApi.saveReponseType.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    render(<SavParametresPage />)
    await user.click(screen.getByRole('tab', { name: 'Réponses types' }))
    fireEvent.change(await screen.findByPlaceholderText('Titre'), { target: { value: 'Relance client' } })
    fireEvent.change(screen.getByPlaceholderText('Corps du message'), { target: { value: 'Bonjour {client}...' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))
    await waitFor(() => expect(savApi.saveReponseType).toHaveBeenCalledWith(
      null, expect.objectContaining({ titre: 'Relance client', corps: 'Bonjour {client}...' })))
  })

  describe('WIR30 — onglet SLA / Automatisation', () => {
    it('charge les réglages via GET /sav/sla-settings/ et affiche les 7 toggles', async () => {
      const user = userEvent.setup()
      render(<SavParametresPage />)
      await user.click(screen.getByRole('tab', { name: 'SLA / Automatisation' }))
      await waitFor(() => expect(api.get).toHaveBeenCalledWith('/sav/sla-settings/'))
      expect(await screen.findByRole('switch',
        { name: 'Génération automatique des visites préventives dues' })).toBeInTheDocument()
      expect(screen.getByRole('switch',
        { name: 'Escalader au responsable à la violation du SLA' })).toBeInTheDocument()
    })

    it("active generation_auto_visites et persiste via POST /sav/sla-settings/", async () => {
      const user = userEvent.setup()
      render(<SavParametresPage />)
      await user.click(screen.getByRole('tab', { name: 'SLA / Automatisation' }))
      const toggle = await screen.findByRole('switch',
        { name: 'Génération automatique des visites préventives dues' })
      expect(toggle).toHaveAttribute('aria-checked', 'false')
      await user.click(toggle)
      expect(toggle).toHaveAttribute('aria-checked', 'true')
      await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
      await waitFor(() => expect(api.post).toHaveBeenCalledWith(
        '/sav/sla-settings/', expect.objectContaining({ generation_auto_visites: true })))
    })
  })
})
