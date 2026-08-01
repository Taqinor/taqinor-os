import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  appliquer: vi.fn(),
  update: vi.fn(),
  create: vi.fn(),
  dossiersImpactes: vi.fn(),
}))

vi.mock('../../../api/aoApi', () => ({
  default: {
    bibliotheque: {
      list: mocks.list,
      appliquer: mocks.appliquer,
      update: mocks.update,
      create: mocks.create,
      dossiersImpactes: mocks.dossiersImpactes,
    },
  },
}))

import BibliothequePage from './BibliothequePage'

const KITS = [{ id: 1, nom: 'Table dos-à-dos 2 modules', description: 'Kit standard AO.' }]
const TEXTES = [{ id: 5, nom: 'Clause de réserve', corps: 'Texte normatif initial.', dossiers_utilisant_count: 3 }]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockImplementation((params) => {
    if (params?.type === 'texte_normalise') return Promise.resolve({ data: TEXTES })
    return Promise.resolve({ data: KITS })
  })
  mocks.appliquer.mockResolvedValue({ data: {} })
  mocks.update.mockResolvedValue({ data: {} })
  mocks.dossiersImpactes.mockResolvedValue({
    data: [{ id: 1, reference: 'AO-2026-001' }, { id: 2, reference: 'AO-2026-002' }],
  })
})

describe('BibliothequePage', () => {
  it('charge les kits de pose par défaut (type=kit)', async () => {
    render(<BibliothequePage />)
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ type: 'kit' }))
    expect(await screen.findByText('Table dos-à-dos 2 modules')).toBeInTheDocument()
  })

  it('changer de catégorie recharge avec le bon type', async () => {
    render(<BibliothequePage />)
    await screen.findByText('Table dos-à-dos 2 modules')
    fireEvent.click(screen.getByRole('radio', { name: 'Textes normalisés' }))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ type: 'texte_normalise' }))
    expect(await screen.findByText('Clause de réserve')).toBeInTheDocument()
  })

  it('« Appliquer » un kit est UN clic → UN appel réseau tracé côté serveur', async () => {
    render(<BibliothequePage />)
    await screen.findByText('Table dos-à-dos 2 modules')
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(mocks.appliquer).toHaveBeenCalledWith(1))
    expect(mocks.appliquer).toHaveBeenCalledTimes(1)
  })

  it('« Modifier » un texte normalisé partagé affiche les dossiers impactés AVANT toute validation', async () => {
    render(<BibliothequePage />)
    await screen.findByText('Table dos-à-dos 2 modules')
    fireEvent.click(screen.getByRole('radio', { name: 'Textes normalisés' }))
    await screen.findByText('Clause de réserve')
    fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
    await waitFor(() => expect(mocks.dossiersImpactes).toHaveBeenCalledWith(5))
    expect(await screen.findByText('AO-2026-001')).toBeInTheDocument()
    expect(screen.getByText('AO-2026-002')).toBeInTheDocument()
  })

  it('enregistrer un texte modifié fait un PATCH sur le MÊME id — jamais create() (aucune duplication silencieuse)', async () => {
    render(<BibliothequePage />)
    fireEvent.click(await screen.findByRole('radio', { name: 'Textes normalisés' }))
    await screen.findByText('Clause de réserve')
    fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
    await screen.findByText('AO-2026-001') // dossiers impactés chargés
    const textarea = screen.getByLabelText('Corps du texte normalisé')
    fireEvent.change(textarea, { target: { value: 'Texte normatif révisé.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(5, { corps: 'Texte normatif révisé.' }))
    expect(mocks.create).not.toHaveBeenCalled()
  })
})
