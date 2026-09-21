import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR262 — chatter sinistre invisible et note de police impossible.
   - PoliceDetail avait déjà un fil (lecture seule) : on vérifie le composeur
     ajouté (bouton inactif à vide, publication, rechargement du fil).
   - SinistresPage n'avait AUCUN fil : on vérifie qu'il apparaît (transition
     de statut visible via le diff de champ) avec le même rendu, et son
     propre composeur. */

const api = {
  getAssureurs: vi.fn(() => Promise.resolve({ data: [] })),
  getCourtiers: vi.fn(() => Promise.resolve({ data: [] })),
  getPolice: vi.fn(() => Promise.resolve({
    data: { id: 7, numero_police: 'P-1', type_police: 'rc_pro', statut: 'active' },
  })),
  getGaranties: vi.fn(() => Promise.resolve({ data: [] })),
  getActifsCouverts: vi.fn(() => Promise.resolve({ data: [] })),
  getEcheancesPrime: vi.fn(() => Promise.resolve({ data: [] })),
  getAttestations: vi.fn(() => Promise.resolve({ data: [] })),
  getPolices: vi.fn(() => Promise.resolve({ data: [] })),
  getSinistres: vi.fn(() => Promise.resolve({
    data: [{ id: 9, numero_dossier: 'S-1', type_sinistre: 'vol', statut: 'en_expertise' }],
  })),
  getSinistre: vi.fn(() => Promise.resolve({ data: { id: 9, indemnisation: null } })),
  marquerSinistreConteste: vi.fn(),

  // Chatter — les deux fils sous test.
  getPoliceHistorique: vi.fn(),
  noterPolice: vi.fn(),
  getSinistreHistorique: vi.fn(),
  noterSinistre: vi.fn(),
}
vi.mock('./assurancesApi', () => ({ default: api }))

const PoliceDetail = (await import('./PoliceDetail')).default
const SinistresPage = (await import('./SinistresPage')).default

function withProviders(ui, initialEntries = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

const HISTORIQUE_POLICE = [
  { id: 1, kind: 'field_change', field: 'statut', field_label: 'Statut', old_value: 'brouillon', new_value: 'active', created_at: '2026-08-01T09:00:00Z' },
]
const HISTORIQUE_SINISTRE = [
  { id: 2, kind: 'field_change', field: 'statut', field_label: 'Statut', old_value: 'declare', new_value: 'en_expertise', created_at: '2026-08-02T09:00:00Z' },
]

beforeEach(() => {
  vi.clearAllMocks()
  api.getPoliceHistorique.mockResolvedValue({ data: HISTORIQUE_POLICE })
  api.getSinistreHistorique.mockResolvedValue({ data: HISTORIQUE_SINISTRE })
  api.noterPolice.mockResolvedValue({ data: { id: 100, kind: 'note', body: 'Renouvellement à préparer.' } })
  api.noterSinistre.mockResolvedValue({ data: { id: 101, kind: 'note', body: 'Expert mandaté.' } })
})

describe('WIR262 — PoliceDetail : composeur de note sur le fil existant', () => {
  it('affiche la transition de statut dans le fil', async () => {
    withProviders(
      <Routes><Route path="/assurances/:id" element={<PoliceDetail />} /></Routes>,
      ['/assurances/7'],
    )
    expect(await screen.findByText(/Statut : brouillon → active/)).toBeInTheDocument()
  })

  it('le bouton de publication est inactif tant que la note est vide', async () => {
    withProviders(
      <Routes><Route path="/assurances/:id" element={<PoliceDetail />} /></Routes>,
      ['/assurances/7'],
    )
    const bouton = await screen.findByRole('button', { name: 'Publier la note' })
    expect(bouton).toBeDisabled()
  })

  it('publie une note et recharge le fil', async () => {
    const user = userEvent.setup()
    withProviders(
      <Routes><Route path="/assurances/:id" element={<PoliceDetail />} /></Routes>,
      ['/assurances/7'],
    )
    await screen.findByRole('button', { name: 'Publier la note' })

    await user.type(screen.getByLabelText('Nouvelle note'), 'Renouvellement à préparer.')
    // La note écrite au serveur remonte en tête du fil : le mock du second
    // appel getPoliceHistorique() (déclenché par le reload) simule ce tri.
    api.getPoliceHistorique.mockResolvedValueOnce({
      data: [
        { id: 100, kind: 'note', body: 'Renouvellement à préparer.', created_at: '2026-08-26T10:00:00Z' },
        ...HISTORIQUE_POLICE,
      ],
    })
    await user.click(screen.getByRole('button', { name: 'Publier la note' }))

    await waitFor(() => expect(api.noterPolice).toHaveBeenCalledWith(
      '7', 'Renouvellement à préparer.',
    ))
    await waitFor(() => expect(api.getPoliceHistorique).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('Renouvellement à préparer.')).toBeInTheDocument()
  })
})

describe('WIR262 — SinistresPage : fil et composeur (jusqu’ici inexistants)', () => {
  it('affiche la transition de statut du sinistre sélectionné', async () => {
    const user = userEvent.setup()
    withProviders(<SinistresPage />)
    const rows = await screen.findAllByText('S-1')
    await user.click(rows[0])

    expect(await screen.findByText(/Statut : declare → en_expertise/)).toBeInTheDocument()
    await waitFor(() => expect(api.getSinistreHistorique).toHaveBeenCalledWith(9))
  })

  it('le bouton de publication est inactif tant que la note est vide', async () => {
    const user = userEvent.setup()
    withProviders(<SinistresPage />)
    const rows = await screen.findAllByText('S-1')
    await user.click(rows[0])

    const bouton = await screen.findByRole('button', { name: 'Publier la note' })
    expect(bouton).toBeDisabled()
  })

  it('publie une note sur le sinistre et recharge le fil', async () => {
    const user = userEvent.setup()
    withProviders(<SinistresPage />)
    const rows = await screen.findAllByText('S-1')
    await user.click(rows[0])
    await screen.findByRole('button', { name: 'Publier la note' })

    await user.type(screen.getByLabelText('Nouvelle note sinistre'), 'Expert mandaté.')
    api.getSinistreHistorique.mockResolvedValueOnce({
      data: [
        { id: 101, kind: 'note', body: 'Expert mandaté.', created_at: '2026-08-26T10:00:00Z' },
        ...HISTORIQUE_SINISTRE,
      ],
    })
    await user.click(screen.getByRole('button', { name: 'Publier la note' }))

    await waitFor(() => expect(api.noterSinistre).toHaveBeenCalledWith(9, 'Expert mandaté.'))
    expect(await screen.findByText('Expert mandaté.')).toBeInTheDocument()
  })
})
