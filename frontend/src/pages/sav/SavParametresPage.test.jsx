import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

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

import savApi from '../../api/savApi'
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
    render(<SavParametresPage />)
    fireEvent.click(screen.getByRole('tab', { name: 'Réponses types' }))
    fireEvent.change(await screen.findByPlaceholderText('Titre'), { target: { value: 'Relance client' } })
    fireEvent.change(screen.getByPlaceholderText('Corps du message'), { target: { value: 'Bonjour {client}...' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))
    await waitFor(() => expect(savApi.saveReponseType).toHaveBeenCalledWith(
      null, expect.objectContaining({ titre: 'Relance client', corps: 'Bonjour {client}...' })))
  })
})
