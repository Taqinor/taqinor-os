import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   ZSTK12 — Nomenclatures de code-barres (Paramètres → Stock) : CRUD des
   nomenclatures (Default/GS1) + leurs règles motif → type d'entité.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getNomenclaturesCodeBarres: vi.fn(),
    createNomenclatureCodeBarres: vi.fn(),
    updateNomenclatureCodeBarres: vi.fn(),
    deleteNomenclatureCodeBarres: vi.fn(),
    createRegleCodeBarres: vi.fn(),
    updateRegleCodeBarres: vi.fn(),
    deleteRegleCodeBarres: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import NomenclaturesCodeBarresSection from './NomenclaturesCodeBarresSection.jsx'

function wrap(node) {
  return render(<ThemeProvider>{node}</ThemeProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
})

describe('ZSTK12 — liste des nomenclatures', () => {
  it('affiche les nomenclatures existantes avec leurs règles', async () => {
    stockApi.getNomenclaturesCodeBarres.mockResolvedValue({
      data: [{
        id: 1, nom: 'Magasin interne', type_nomenclature: 'default', actif: true,
        regles: [{ id: 5, nomenclature: 1, motif: '22', est_regex: false, encode: 'produit', priorite: 100 }],
      }],
    })
    wrap(<NomenclaturesCodeBarresSection />)
    expect(await screen.findByText('Magasin interne')).toBeInTheDocument()
    expect(screen.getByText('22')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('sans nomenclature : état vide honnête', async () => {
    stockApi.getNomenclaturesCodeBarres.mockResolvedValue({ data: [] })
    wrap(<NomenclaturesCodeBarresSection />)
    expect(await screen.findByText('Aucune nomenclature')).toBeInTheDocument()
  })

  it('crée une nomenclature', async () => {
    stockApi.getNomenclaturesCodeBarres.mockResolvedValue({ data: [] })
    stockApi.createNomenclatureCodeBarres.mockResolvedValue({ data: { id: 2 } })
    wrap(<NomenclaturesCodeBarresSection />)
    await screen.findByText('Aucune nomenclature')
    fireEvent.change(screen.getByPlaceholderText('Nom de la nomenclature'), { target: { value: 'GS1 fournisseur' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer/ }))
    await waitFor(() => expect(stockApi.createNomenclatureCodeBarres).toHaveBeenCalledWith({
      nom: 'GS1 fournisseur', type_nomenclature: 'default',
    }))
  })

  it('active/désactive une nomenclature', async () => {
    stockApi.getNomenclaturesCodeBarres.mockResolvedValue({
      data: [{ id: 1, nom: 'Magasin interne', type_nomenclature: 'default', actif: false, regles: [] }],
    })
    stockApi.updateNomenclatureCodeBarres.mockResolvedValue({ data: {} })
    wrap(<NomenclaturesCodeBarresSection />)
    await screen.findByText('Magasin interne')
    fireEvent.click(screen.getByRole('button', { name: 'Activer' }))
    await waitFor(() => expect(stockApi.updateNomenclatureCodeBarres).toHaveBeenCalledWith(1, { actif: true }))
  })

  it('ajoute une règle à une nomenclature', async () => {
    stockApi.getNomenclaturesCodeBarres.mockResolvedValue({
      data: [{ id: 1, nom: 'Magasin interne', type_nomenclature: 'default', actif: true, regles: [] }],
    })
    stockApi.createRegleCodeBarres.mockResolvedValue({ data: { id: 9 } })
    wrap(<NomenclaturesCodeBarresSection />)
    await screen.findByText('Magasin interne')
    fireEvent.change(screen.getByPlaceholderText('Motif (ex. 22)'), { target: { value: '99' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter/ }))
    await waitFor(() => expect(stockApi.createRegleCodeBarres).toHaveBeenCalledWith({
      nomenclature: 1, motif: '99', est_regex: false, encode: 'produit', priorite: 100,
    }))
  })
})
