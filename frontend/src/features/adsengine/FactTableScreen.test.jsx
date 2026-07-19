import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB6/AGEN1 — Table des faits : cycle brouillon → édition des FactEntry →
   publication → diff entre versions, entièrement piloté par l'API mockée. */

const mocks = vi.hoisted(() => ({
  tablesList: vi.fn(),
  tablesCreate: vi.fn(),
  tablesPublish: vi.fn(),
  entriesList: vi.fn(),
  entriesCreate: vi.fn(),
  entriesUpdate: vi.fn(),
  entriesRemove: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    factTables: {
      list: mocks.tablesList, create: mocks.tablesCreate, publish: mocks.tablesPublish,
    },
    factEntries: {
      list: mocks.entriesList, create: mocks.entriesCreate,
      update: mocks.entriesUpdate, remove: mocks.entriesRemove,
    },
  },
}))

import FactTableScreen from './FactTableScreen'
import { diffFactEntries } from './adsengine'

const renderScreen = () => render(<MemoryRouter><FactTableScreen /></MemoryRouter>)

const TABLES = [
  { id: 2, version: 2, statut: 'brouillon', created_at: '2026-07-15' },
  { id: 1, version: 1, statut: 'publiee', created_at: '2026-07-01' },
]
const ENTRIES = [
  { id: 10, table: 1, cle: 'prix_kwc', valeur: '9500', unite: 'MAD', source: 'catalogue', verifie_le: '2026-07-01' },
  { id: 11, table: 1, cle: 'garantie_panneau', valeur: '25', unite: 'ans', source: 'fiche produit', verifie_le: '2026-07-01' },
  { id: 20, table: 2, cle: 'prix_kwc', valeur: '9200', unite: 'MAD', source: 'catalogue', verifie_le: '2026-07-15' },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.tablesList.mockResolvedValue({ data: TABLES })
  mocks.entriesList.mockResolvedValue({ data: ENTRIES })
  mocks.tablesCreate.mockResolvedValue({ data: { id: 3, version: 3, statut: 'brouillon' } })
  mocks.tablesPublish.mockResolvedValue({ data: { id: 2, version: 2, statut: 'publiee' } })
  mocks.entriesCreate.mockResolvedValue({ data: { id: 30 } })
  mocks.entriesUpdate.mockResolvedValue({ data: {} })
  mocks.entriesRemove.mockResolvedValue({ data: {} })
})

describe('diffFactEntries (helper pur)', () => {
  it('détecte ajouts, retraits et changements par clé', () => {
    const from = [{ cle: 'a', valeur: '1', unite: '' }, { cle: 'b', valeur: '2', unite: '' }]
    const to = [{ cle: 'a', valeur: '1', unite: '' }, { cle: 'c', valeur: '3', unite: '' }]
    const diff = diffFactEntries(from, to)
    expect(diff.added.map(e => e.cle)).toEqual(['c'])
    expect(diff.removed.map(e => e.cle)).toEqual(['b'])
    expect(diff.changed).toEqual([])
  })

  it('détecte un changement de valeur pour la même clé', () => {
    const from = [{ cle: 'prix', valeur: '9500', unite: 'MAD' }]
    const to = [{ cle: 'prix', valeur: '9200', unite: 'MAD' }]
    const diff = diffFactEntries(from, to)
    expect(diff.changed).toHaveLength(1)
    expect(diff.changed[0]).toMatchObject({ cle: 'prix' })
  })
})

describe('FactTableScreen (PUB6/AGEN1)', () => {
  it('sélectionne la version publiée par défaut et liste ses faits', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.tablesList).toHaveBeenCalled())
    expect(await screen.findByText('Version 1 — Publiée')).toBeInTheDocument()
    const rows = screen.getAllByTestId('ae-facttable-entry-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('prix_kwc')
    expect(rows[0]).toHaveTextContent('9500')
  })

  it('changer de version dans la liste affiche ses propres faits', async () => {
    renderScreen()
    await screen.findByText('Version 1 — Publiée')
    fireEvent.click(screen.getByTestId('ae-facttable-version-2'))
    expect(await screen.findByText('Version 2 — Brouillon')).toBeInTheDocument()
    const rows = screen.getAllByTestId('ae-facttable-entry-row')
    expect(rows).toHaveLength(1)
    expect(rows[0]).toHaveTextContent('9200')
    // Un brouillon peut être publié ; une version déjà publiée non.
    expect(screen.getByTestId('ae-facttable-publish')).toBeInTheDocument()
  })

  it('« Nouveau brouillon » crée une version et recharge', async () => {
    renderScreen()
    await screen.findByText('Version 1 — Publiée')
    fireEvent.click(screen.getByTestId('ae-facttable-new-draft'))
    await waitFor(() => expect(mocks.tablesCreate).toHaveBeenCalledWith({}))
    expect(await screen.findByTestId('ae-facttable-msg')).toHaveTextContent('v3')
    expect(mocks.tablesList).toHaveBeenCalledTimes(2) // chargement initial + rechargement
  })

  it('« Publier » appelle factTables.publish sur la version sélectionnée', async () => {
    renderScreen()
    await screen.findByText('Version 1 — Publiée')
    fireEvent.click(screen.getByTestId('ae-facttable-version-2'))
    await screen.findByText('Version 2 — Brouillon')
    fireEvent.click(screen.getByTestId('ae-facttable-publish'))
    await waitFor(() => expect(mocks.tablesPublish).toHaveBeenCalledWith(2))
  })

  it('ajoute un fait à la version sélectionnée', async () => {
    renderScreen()
    await screen.findByText('Version 1 — Publiée')
    fireEvent.change(screen.getByTestId('ae-facttable-add-cle'), { target: { value: 'prix_batterie' } })
    fireEvent.change(screen.getByTestId('ae-facttable-add-valeur'), { target: { value: '4200' } })
    fireEvent.change(screen.getByTestId('ae-facttable-add-verifie'), { target: { value: '2026-07-18' } })
    fireEvent.click(screen.getByTestId('ae-facttable-add-submit'))
    await waitFor(() => expect(mocks.entriesCreate).toHaveBeenCalledWith({
      cle: 'prix_batterie', valeur: '4200', unite: '', source: '', verifie_le: '2026-07-18', table: 1,
    }))
  })

  it('modifie un fait existant (édition en ligne)', async () => {
    renderScreen()
    await screen.findByText('Version 1 — Publiée')
    fireEvent.click(screen.getByTestId('ae-facttable-edit-10'))
    fireEvent.change(screen.getByTestId('ae-facttable-edit-valeur-10'), { target: { value: '9600' } })
    fireEvent.click(screen.getByTestId('ae-facttable-save-10'))
    await waitFor(() => expect(mocks.entriesUpdate).toHaveBeenCalledWith(10, expect.objectContaining({
      valeur: '9600',
    })))
  })

  it('supprime un fait', async () => {
    renderScreen()
    await screen.findByText('Version 1 — Publiée')
    fireEvent.click(screen.getByTestId('ae-facttable-delete-11'))
    await waitFor(() => expect(mocks.entriesRemove).toHaveBeenCalledWith(11))
  })

  it('affiche un diff entre la version sélectionnée et une autre', async () => {
    renderScreen()
    await screen.findByText('Version 1 — Publiée')
    fireEvent.click(screen.getByTestId('ae-facttable-version-2'))
    await screen.findByText('Version 2 — Brouillon')
    fireEvent.change(screen.getByTestId('ae-facttable-compare-select'), { target: { value: '1' } })
    const diffPanel = await screen.findByTestId('ae-facttable-diff')
    // v1→v2 : prix_kwc changé (9500→9200), garantie_panneau retiré.
    expect(diffPanel).toHaveTextContent('9500')
    expect(diffPanel).toHaveTextContent('9200')
    expect(screen.getByTestId('ae-facttable-diff-changed')).toBeInTheDocument()
    expect(screen.getByTestId('ae-facttable-diff-removed')).toHaveTextContent('garantie_panneau')
  })

  it('état vide : aucune version', async () => {
    mocks.tablesList.mockResolvedValue({ data: [] })
    mocks.entriesList.mockResolvedValue({ data: [] })
    renderScreen()
    expect(await screen.findByTestId('ae-facttable-versions-empty')).toBeInTheDocument()
    expect(screen.getByTestId('ae-facttable-select-empty')).toBeInTheDocument()
  })
})
