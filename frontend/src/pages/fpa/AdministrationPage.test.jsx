import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* WIR199 — le module FP&A était inamorçable sans l'admin Django : ni cycle ni
   département créable, l'export XLSX orphelin. On vérifie ici la création
   d'un département et d'un cycle, la gouvernance d'un cycle (ouvrir-saisie/
   clore/dupliquer/export) et le gating par les codes fpa_* (WIR173) : la
   création suit `peutEcrireFpa`, la gouvernance des cycles exige
   spécifiquement `fpa_administrer` (`ExigeFpaPermission` côté serveur). */

const getDepartementsTree = vi.fn()
const getDepartements = vi.fn()
const createDepartement = vi.fn()
const updateDepartement = vi.fn()
const getCycles = vi.fn()
const createCycle = vi.fn()
const ouvrirSaisie = vi.fn()
const cloreCycle = vi.fn()
const dupliquerCycle = vi.fn()
const exportCycle = vi.fn()

vi.mock('../../api/fpaApi', () => ({
  default: {
    getDepartementsTree: (...a) => getDepartementsTree(...a),
    getDepartements: (...a) => getDepartements(...a),
    createDepartement: (...a) => createDepartement(...a),
    updateDepartement: (...a) => updateDepartement(...a),
    getCycles: (...a) => getCycles(...a),
    createCycle: (...a) => createCycle(...a),
    ouvrirSaisie: (...a) => ouvrirSaisie(...a),
    cloreCycle: (...a) => cloreCycle(...a),
    dupliquerCycle: (...a) => dupliquerCycle(...a),
    exportCycle: (...a) => exportCycle(...a),
  },
}))

const downloadXlsx = vi.fn()
vi.mock('../../api/importApi', () => ({ downloadXlsx: (...a) => downloadXlsx(...a) }))

const toastSuccess = vi.fn()
const toastError = vi.fn()
vi.mock('../../ui', async (orig) => ({
  ...(await orig()),
  toast: { success: (...a) => toastSuccess(...a), error: (...a) => toastError(...a) },
}))

import AdministrationPage from './AdministrationPage'

function monter({ permissions = [] } = {}) {
  const store = configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'admin', role_nom: 'Administrateur',
        permissions, isAuthenticated: true, loading: false,
      },
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><AdministrationPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

const DEPARTEMENTS = [{ id: 2, code: 'COM', nom: 'Commercial', actif: true }]
const ARBRE = [{ id: 2, code: 'COM', nom: 'Commercial', actif: true, enfants: [] }]
const CYCLES = [
  { id: 1, nom: 'Budget 2027', date_debut: '2027-01-01', date_fin: '2027-12-31', statut: 'brouillon', type_cycle: 'annuel' },
]

beforeEach(() => {
  vi.clearAllMocks()
  getDepartementsTree.mockResolvedValue({ data: ARBRE })
  getDepartements.mockResolvedValue({ data: DEPARTEMENTS })
  getCycles.mockResolvedValue({ data: CYCLES })
  createDepartement.mockResolvedValue({ data: { id: 3 } })
  createCycle.mockResolvedValue({ data: { id: 4 } })
  ouvrirSaisie.mockResolvedValue({ data: {} })
  cloreCycle.mockResolvedValue({ data: {} })
  dupliquerCycle.mockResolvedValue({ data: {} })
  exportCycle.mockResolvedValue({ data: new Blob(['x']) })
})

describe('AdministrationPage — départements et cycles (WIR199)', () => {
  it('crée un département avec fpa_saisir (peutEcrireFpa)', async () => {
    const user = userEvent.setup()
    monter({ permissions: ['fpa_saisir'] })
    await waitFor(() => expect(getDepartementsTree).toHaveBeenCalled())

    await user.type(screen.getByLabelText('Code du département'), 'TECH')
    await user.type(screen.getByLabelText('Nom du département'), 'Technique')
    await user.click(screen.getByRole('button', { name: 'Ajouter un département' }))

    await waitFor(() => expect(createDepartement).toHaveBeenCalledWith({
      code: 'TECH', nom: 'Technique', parent: null,
    }))
    expect(toastSuccess).toHaveBeenCalledWith('Département créé.')
  })

  it('crée un cycle avec fpa_saisir', async () => {
    const user = userEvent.setup()
    monter({ permissions: ['fpa_saisir'] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())

    await user.type(screen.getByLabelText('Nom du cycle'), 'Budget 2028')
    await user.type(screen.getByLabelText('Début du cycle'), '2028-01-01')
    await user.type(screen.getByLabelText('Fin du cycle'), '2028-12-31')
    await user.click(screen.getByRole('button', { name: 'Créer le cycle' }))

    await waitFor(() => expect(createCycle).toHaveBeenCalledWith({
      nom: 'Budget 2028', date_debut: '2028-01-01', date_fin: '2028-12-31', type_cycle: 'annuel',
    }))
    expect(toastSuccess).toHaveBeenCalledWith('Cycle créé.')
  })

  it('masque la création (départements/cycles) sans aucun code fpa_*', async () => {
    monter({ permissions: [] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    expect(screen.queryByLabelText('Nom du département')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Nom du cycle')).not.toBeInTheDocument()
  })

  it('masque la gouvernance des cycles sans fpa_administrer (même avec fpa_saisir)', async () => {
    monter({ permissions: ['fpa_saisir'] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: 'Ouvrir la saisie' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Dupliquer' })).not.toBeInTheDocument()
  })

  it('ouvre la saisie, clôture, duplique et exporte un cycle avec fpa_administrer', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'prompt').mockReturnValue('Budget 2027 (copie)')
    monter({ permissions: ['fpa_administrer'] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())

    await user.click(screen.getByRole('button', { name: 'Ouvrir la saisie' }))
    await waitFor(() => expect(ouvrirSaisie).toHaveBeenCalledWith(1))

    await user.click(screen.getByRole('button', { name: 'Dupliquer' }))
    await waitFor(() => expect(dupliquerCycle).toHaveBeenCalledWith(1, 'Budget 2027 (copie)'))

    await user.click(screen.getByRole('button', { name: 'Exporter XLSX' }))
    await waitFor(() => expect(exportCycle).toHaveBeenCalledWith(1))
    expect(downloadXlsx).toHaveBeenCalledWith(expect.any(Blob), 'synthese_fpa_1.xlsx')
  })

  it('affiche « Clore » uniquement pour un cycle ouvert à la saisie', async () => {
    getCycles.mockResolvedValue({
      data: [{ id: 5, nom: 'Budget 2026', date_debut: '2026-01-01', date_fin: '2026-12-31', statut: 'ouvert_saisie', type_cycle: 'annuel' }],
    })
    monter({ permissions: ['fpa_administrer'] })
    await waitFor(() => expect(getCycles).toHaveBeenCalled())
    const ligne = screen.getByText('Budget 2026').closest('tr')
    expect(within(ligne).getByRole('button', { name: 'Clore' })).toBeInTheDocument()
    expect(within(ligne).queryByRole('button', { name: 'Ouvrir la saisie' })).not.toBeInTheDocument()
  })

  it('renomme et désactive un département avec fpa_saisir', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'prompt').mockReturnValue('Commercial Maroc')
    updateDepartement.mockResolvedValue({ data: {} })
    monter({ permissions: ['fpa_saisir'] })
    await waitFor(() => expect(getDepartementsTree).toHaveBeenCalled())

    await user.click(screen.getByRole('button', { name: 'Renommer' }))
    await waitFor(() => expect(updateDepartement).toHaveBeenCalledWith(2, { nom: 'Commercial Maroc' }))

    await user.click(screen.getByRole('button', { name: 'Désactiver' }))
    await waitFor(() => expect(updateDepartement).toHaveBeenCalledWith(2, { actif: false }))
  })
})
