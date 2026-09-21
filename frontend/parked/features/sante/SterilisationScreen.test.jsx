import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import SterilisationScreen from './SterilisationScreen'

/* PACT114 — Stérilisation des instruments : cycles et traçabilité sanitaire.
   NTSAN23/24 (`apps/sante`) livraient déjà les modèles/endpoints/action
   serveur SANS AUCUN client API santé ni écran. Vérifie : la liste des
   cycles + instruments, la création d'un cycle, et — le point qui compte —
   qu'un cycle NON CONFORME affiche EXACTEMENT la liste de patients renvoyée
   par l'action serveur `patients-concernes/`, sans aucun recalcul local. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const { apiGet, apiPost } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

vi.mock('../../api/axios', () => ({
  default: { get: (...args) => apiGet(...args), post: (...args) => apiPost(...args) },
}))

const CYCLE_CONFORME = {
  id: 1, numero_cycle: 'CYC-001', date_cycle: '2026-08-01T09:00:00Z',
  autoclave_ref: 'AUTOCLAVE-1', statut: 'conforme', operateur: 3,
}
const CYCLE_NON_CONFORME = {
  id: 2, numero_cycle: 'CYC-002', date_cycle: '2026-08-05T09:00:00Z',
  autoclave_ref: 'AUTOCLAVE-1', statut: 'non_conforme', operateur: 3,
}
const INSTRUMENT = { id: 10, cycle: 1, instrument_ref: 'PINCE-01', kit_ref: '' }

beforeEach(() => {
  vi.clearAllMocks()
  apiPost.mockResolvedValue({ data: { id: 99 } })
  apiGet.mockImplementation((url) => {
    if (url === '/sante/cycles-sterilisation/') {
      return Promise.resolve({ data: [CYCLE_CONFORME, CYCLE_NON_CONFORME] })
    }
    if (url === '/sante/instruments-sterilises/') return Promise.resolve({ data: [INSTRUMENT] })
    if (url === '/sante/cycles-sterilisation/2/patients-concernes/') {
      return Promise.resolve({
        data: { count: 2, results: [{ id: 5, nom: 'Alami', prenom: 'Yasmine' }, { id: 6, nom: 'Bennani', prenom: 'Omar' }] },
      })
    }
    return Promise.resolve({ data: [] })
  })
})

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <SterilisationScreen />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('SterilisationScreen (PACT114)', () => {
  it('affiche les cycles et leurs instruments', async () => {
    renderScreen()
    // CYC-001 apparaît aussi comme <option> dans le sélecteur de cycle du
    // formulaire « instruments » : on cible la ligne du tableau des cycles,
    // désambiguïsée par son data-testid, pas le texte brut.
    await waitFor(() => expect(screen.getByTestId('cycle-1')).toBeInTheDocument())
    expect(within(screen.getByTestId('cycle-1')).getByText('CYC-001')).toBeInTheDocument()
    expect(within(screen.getByTestId('cycle-2')).getByText('CYC-002')).toBeInTheDocument()
    expect(screen.getByText('PINCE-01')).toBeInTheDocument()
  })

  it('crée un nouveau cycle de stérilisation', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('cycle-1')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Numéro de cycle'), { target: { value: 'CYC-003' } })
    fireEvent.change(screen.getByLabelText('Date du cycle'), { target: { value: '2026-08-10T10:00' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))

    await waitFor(() => expect(apiPost).toHaveBeenCalledWith('/sante/cycles-sterilisation/', {
      numero_cycle: 'CYC-003', date_cycle: '2026-08-10T10:00', autoclave_ref: '', statut: 'conforme',
    }))
  })

  it('un cycle non conforme affiche EXACTEMENT les patients renvoyés par le serveur (aucun recalcul client)', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('cycle-2')).toBeInTheDocument())

    const ligneNonConforme = screen.getByTestId('cycle-2')
    fireEvent.click(
      ligneNonConforme.querySelector('button'),
    )

    await waitFor(() => expect(apiGet).toHaveBeenCalledWith('/sante/cycles-sterilisation/2/patients-concernes/'))
    const liste = await screen.findByTestId('patients-concernes-2')
    expect(liste.textContent).toContain('Alami Yasmine')
    expect(liste.textContent).toContain('Bennani Omar')

    // Le cycle CONFORME, lui, ne propose aucun bouton « patients concernés ».
    const ligneConforme = screen.getByTestId('cycle-1')
    expect(ligneConforme.textContent).not.toMatch(/patients concernés/i)
  })
})
