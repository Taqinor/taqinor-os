import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR56 — création de police + garantie + sinistre + indemnisation depuis l'UI.
   Vérifie que les boutons jusqu'ici morts appellent bien les endpoints. */

const navigateMock = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => navigateMock }
})

const api = {
  getAssureurs: vi.fn(() => Promise.resolve({ data: [{ id: 3, raison_sociale: 'AXA' }] })),
  getCourtiers: vi.fn(() => Promise.resolve({ data: [] })),
  createPolice: vi.fn(() => Promise.resolve({ data: { id: 42 } })),
  getPolice: vi.fn(() => Promise.resolve({ data: { id: 7, numero_police: 'P-1', type_police: 'rc_pro', statut: 'active' } })),
  getGaranties: vi.fn(() => Promise.resolve({ data: [] })),
  getActifsCouverts: vi.fn(() => Promise.resolve({ data: [] })),
  getEcheancesPrime: vi.fn(() => Promise.resolve({ data: [] })),
  getPoliceHistorique: vi.fn(() => Promise.resolve({ data: [] })),
  getAttestations: vi.fn(() => Promise.resolve({ data: [] })),
  createGarantie: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  getPolices: vi.fn(() => Promise.resolve({ data: [{ id: 7, numero_police: 'P-1', type_police: 'rc_pro' }] })),
  getSinistres: vi.fn(() => Promise.resolve({ data: [{ id: 9, numero_dossier: 'S-1', type_sinistre: 'vol', statut: 'declare' }] })),
  getSinistre: vi.fn(() => Promise.resolve({ data: { id: 9, indemnisation: null } })),
  createSinistre: vi.fn(() => Promise.resolve({ data: { id: 10 } })),
  enregistrerIndemnisation: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  marquerSinistreConteste: vi.fn(() => Promise.resolve({ data: {} })),
}
vi.mock('./assurancesApi', () => ({ default: api }))

const PoliceForm = (await import('./PoliceForm')).default
const PoliceDetail = (await import('./PoliceDetail')).default
const SinistresPage = (await import('./SinistresPage')).default

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui, initialEntries = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('WIR56 — PoliceForm', () => {
  it('crée une police et redirige vers sa fiche', async () => {
    const user = userEvent.setup()
    withProviders(<PoliceForm />)

    await user.selectOptions(await screen.findByLabelText('Assureur'), '3')
    await user.type(screen.getByLabelText('N° police'), 'P-2024-01')
    await user.click(screen.getByRole('button', { name: 'Créer la police' }))

    await waitFor(() => expect(api.createPolice).toHaveBeenCalledWith(
      expect.objectContaining({ assureur: 3, numero_police: 'P-2024-01' }),
    ))
    expect(navigateMock).toHaveBeenCalledWith('/assurances/42')
  })
})

describe('WIR56 — PoliceDetail garantie', () => {
  it('ajoute une garantie depuis l\'onglet Garanties', async () => {
    const user = userEvent.setup()
    withProviders(
      <Routes><Route path="/assurances/:id" element={<PoliceDetail />} /></Routes>,
      ['/assurances/7'],
    )

    await user.click(await screen.findByRole('button', { name: /Ajouter une garantie/ }))
    await user.type(screen.getByLabelText('Libellé de la garantie'), 'Incendie')
    await user.click(screen.getByRole('button', { name: 'Ajouter' }))

    await waitFor(() => expect(api.createGarantie).toHaveBeenCalledWith(
      expect.objectContaining({ police: 7, libelle_garantie: 'Incendie' }),
    ))
  })
})

describe('WIR56 — Sinistres', () => {
  it('déclare un nouveau sinistre', async () => {
    const user = userEvent.setup()
    withProviders(<SinistresPage />)

    await user.click(await screen.findByRole('button', { name: 'Nouveau sinistre' }))
    await user.selectOptions(await screen.findByLabelText('Police concernée'), '7')
    await user.type(screen.getByLabelText('Nature du sinistre'), 'Effraction dépôt')
    await user.click(screen.getByRole('button', { name: 'Déclarer le sinistre' }))

    await waitFor(() => expect(api.createSinistre).toHaveBeenCalledWith(
      expect.objectContaining({ police: 7, nature_sinistre: 'Effraction dépôt' }),
    ))
  })

  it('enregistre une indemnisation sur le sinistre sélectionné', async () => {
    const user = userEvent.setup()
    withProviders(<SinistresPage />)

    const rows = await screen.findAllByText('S-1')
    await user.click(rows[0])
    await user.type(await screen.findByLabelText('Montant réclamé'), '10000')
    await user.type(screen.getByLabelText('Montant indemnisé'), '8000')
    await user.click(screen.getByRole('button', { name: /Enregistrer l'indemnisation/ }))

    await waitFor(() => expect(api.enregistrerIndemnisation).toHaveBeenCalledWith(
      9, expect.objectContaining({ montant_reclame: 10000, montant_indemnise: 8000 }),
    ))
  })
})
