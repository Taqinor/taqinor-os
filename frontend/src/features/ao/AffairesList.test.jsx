import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  dupliquer: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/aoApi', () => ({
  default: {
    affaires: {
      list: mocks.list,
      dupliquer: mocks.dupliquer,
      update: mocks.update,
      remove: mocks.remove,
    },
  },
}))

import AffairesList from './AffairesList'

const renderScreen = () => render(<MemoryRouter><AffairesList /></MemoryRouter>)

const ROWS = [
  {
    id: 1, reference: 'AO-2026-001', objet: 'Centrale solaire école',
    acheteur: 'Commune X', type_marche: 'public', type_marche_display: 'Public',
    lot: 'Lot 1', date_limite: '2026-09-15', montant_estime: 1500000,
    statut: 'depose', capacite_engagement_label: '3/5 équipes',
    dossier_completude: 80,
  },
  {
    id: 2, reference: 'AO-2026-002', objet: 'Pompage agricole',
    acheteur: 'ORMVA', type_marche: 'public', type_marche_display: 'Public',
    lot: '', date_limite: null, montant_estime: 420000,
    statut: 'gagne', capacite_engagement_label: '',
    dossier_completude: null,
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: ROWS })
  mocks.dupliquer.mockResolvedValue({ data: { id: 99 } })
  mocks.update.mockResolvedValue({ data: {} })
})

describe('AffairesList', () => {
  it('charge les affaires via aoApi.affaires.list() (useResource, aucun fetch manuel)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(await screen.findByText('AO-2026-001')).toBeInTheDocument()
    expect(screen.getByText('AO-2026-002')).toBeInTheDocument()
  })

  it('affiche objet, acheteur, montant estimé et la pastille de statut de chaque affaire', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    expect(screen.getByText('Centrale solaire école')).toBeInTheDocument()
    expect(screen.getByText('Commune X')).toBeInTheDocument()
    expect(screen.getByText('Déposé')).toBeInTheDocument()
    expect(screen.getByText('Gagné')).toBeInTheDocument()
  })

  it('capacité vs engagement et complétude du dossier : « — » quand le champ backend est absent (jamais un calcul de substitution)', async () => {
    renderScreen()
    await screen.findByText('AO-2026-002')
    const row2 = screen.getByText('AO-2026-002').closest('tr')
    expect(row2).not.toBeNull()
    expect(row2.textContent).toContain('—')
  })

  it('« Dupliquer » appelle aoApi.affaires.dupliquer() (AOF130, service réel) et navigue vers la copie', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    const row1 = screen.getByText('AO-2026-001').closest('tr')
    // RowActions (DataTable) rend chaque action à la fois en icône rapide
    // (aria-label = label de l'action) ET dans le menu kebab persistant —
    // l'icône rapide suffit, pas besoin d'ouvrir le menu Radix dans le test.
    fireEvent.click(within(row1).getByLabelText('Dupliquer'))
    await waitFor(() => expect(mocks.dupliquer).toHaveBeenCalledWith(1))
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledWith('/ao/affaires/99'))
  })

  it('« Archiver » appelle update(id, { archive: true }) — JAMAIS remove() (archivage logique)', async () => {
    renderScreen()
    await screen.findByText('AO-2026-001')
    const row1 = screen.getByText('AO-2026-001').closest('tr')
    fireEvent.click(within(row1).getByLabelText('Archiver'))
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(1, { archive: true }))
    expect(mocks.remove).not.toHaveBeenCalled()
  })

  it('cliquer une ligne navigue vers la fiche affaire', async () => {
    renderScreen()
    const cell = await screen.findByText('AO-2026-001')
    fireEvent.click(cell.closest('tr'))
    expect(mocks.navigate).toHaveBeenCalledWith('/ao/affaires/1')
  })
})

// ── Garde de source : « zéro useState/useEffect de fetch » (Done AOF170). ──
describe('AffairesList.jsx — contrat de source', () => {
  const here = dirname(fileURLToPath(import.meta.url))
  const src = readFileSync(join(here, 'AffairesList.jsx'), 'utf8')

  it('n’importe ni useState ni useEffect de React (données 100% via useResource)', () => {
    expect(src).not.toMatch(/\buseState\b/)
    expect(src).not.toMatch(/\buseEffect\b/)
  })

  it('utilise useResource + aoApi, jamais un axios.get direct', () => {
    expect(src).toMatch(/from '\.\.\/\.\.\/hooks\/useResource'/)
    expect(src).toMatch(/aoApi\.affaires\.list\(\)/)
    expect(src).not.toMatch(/axios\.get/)
  })

  it('persiste tri/filtre en URL (persistToUrl + urlKey) et déclare des vues sauvegardées', () => {
    expect(src).toMatch(/persistToUrl/)
    expect(src).toMatch(/urlKey="ao-affaires"/)
    expect(src).toMatch(/savedViews=\{SAVED_VIEWS\}/)
  })
})
