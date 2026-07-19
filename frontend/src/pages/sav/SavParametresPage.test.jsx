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
    // WIR119 — modèles de feuille de maintenance.
    getWorksheetModeles: vi.fn(() => Promise.resolve({ data: [] })),
    saveWorksheetModele: vi.fn(() => Promise.resolve({ data: {} })),
    deleteWorksheetModele: vi.fn(() => Promise.resolve({ data: {} })),
    // WIR117 — compatibilités pièces (picker compatibles d'abord).
    getCompatibilitesPiece: vi.fn(() => Promise.resolve({ data: [] })),
    saveCompatibilitePiece: vi.fn(),
    deleteCompatibilitePiece: vi.fn(),
  },
}))

// WIR30/WIR117 — GET/POST /sav/sla-settings/ + GET /stock/produits/ (api axios
// direct, hors savApi). Produits renvoyés en tableau pour le picker WIR117.
vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(
      url && url.includes('/stock/produits/')
        ? { data: [{ id: 1, nom: 'Onduleur', sku: 'OND' }, { id: 2, nom: 'Carte', sku: 'CRT' }] }
        : { data: {} },
    )),
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

  describe('WIR117 — catégories d\'équipement + pièces compatibles', () => {
    it('ajoute une catégorie avec alias e-mail (champ jusqu\'ici non éditable)', async () => {
      savApi.saveCategorieEquipement.mockResolvedValue({ data: {} })
      const user = userEvent.setup()
      render(<SavParametresPage />)
      await user.click(screen.getByRole('tab', { name: "Catégories d'équipement" }))
      fireEvent.change(await screen.findByPlaceholderText('Nouvelle catégorie…'),
        { target: { value: 'Batteries' } })
      fireEvent.change(screen.getByPlaceholderText('Alias e-mail (optionnel)…'),
        { target: { value: 'sav-batt@x.ma' } })
      fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))
      await waitFor(() => expect(savApi.saveCategorieEquipement).toHaveBeenCalledWith(
        null, expect.objectContaining({ nom: 'Batteries', alias_email: 'sav-batt@x.ma' })))
    })

    it('ajoute une compatibilité pièce (produit d\'équipement → pièce)', async () => {
      savApi.saveCompatibilitePiece.mockResolvedValue({ data: {} })
      const user = userEvent.setup()
      render(<SavParametresPage />)
      await user.click(screen.getByRole('tab', { name: 'Pièces compatibles' }))

      await user.click(await screen.findByRole('combobox', { name: "Produit d'équipement" }))
      await user.click(await screen.findByRole('option', { name: 'Onduleur (OND)' }))
      await user.click(screen.getByRole('combobox', { name: 'Pièce compatible' }))
      await user.click(await screen.findByRole('option', { name: 'Carte (CRT)' }))
      fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))

      await waitFor(() => expect(savApi.saveCompatibilitePiece).toHaveBeenCalledWith(
        null, expect.objectContaining({ produit_equipement: '1', piece: '2' })))
    })
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

  describe('WIR119 — onglet Feuilles de maintenance', () => {
    it('crée un modèle de feuille de maintenance', async () => {
      const user = userEvent.setup()
      render(<SavParametresPage />)
      await user.click(screen.getByRole('tab', { name: 'Feuilles de maintenance' }))
      fireEvent.change(await screen.findByPlaceholderText('Nom du modèle'), { target: { value: 'Visite préventive' } })
      fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))
      await waitFor(() => expect(savApi.saveWorksheetModele).toHaveBeenCalledWith(
        null, expect.objectContaining({ nom: 'Visite préventive', champs: [], actif: true })))
    })
  })
})
