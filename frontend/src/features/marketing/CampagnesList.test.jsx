import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  campagnesList: vi.fn(),
  campagnesCreate: vi.fn(),
  listesList: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    campagnes: { list: mocks.campagnesList, create: mocks.campagnesCreate },
    listes: { list: mocks.listesList },
  },
}))

import CampagnesList from './CampagnesList'

const renderScreen = () => render(
  <MemoryRouter><CampagnesList /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.listesList.mockResolvedValue({ data: [] })
  mocks.campagnesList.mockResolvedValue({
    data: [
      { id: 1, nom: 'Relance été', canal: 'email', canal_display: 'Email',
        statut: 'brouillon', statut_display: 'Brouillon', nb_envois: 0,
        taux_ouverture_pct: 0 },
      { id: 2, nom: 'Promo agricole', canal: 'sms', canal_display: 'SMS',
        statut: 'envoyee', statut_display: 'Envoyée', nb_envois: 120,
        taux_ouverture_pct: 42.5 },
    ],
  })
})

describe('CampagnesList', () => {
  it('affiche les campagnes chargées', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.campagnesList).toHaveBeenCalled())
    expect(await screen.findByText('Relance été')).toBeInTheDocument()
    expect(screen.getByText('Promo agricole')).toBeInTheDocument()
  })

  it('le filtre statut réduit la liste affichée sans nouvel appel réseau', async () => {
    renderScreen()
    await screen.findByText('Relance été')
    fireEvent.change(screen.getByTestId('campagnes-filtre-statut'),
      { target: { value: 'envoyee' } })
    expect(screen.queryByText('Relance été')).toBeNull()
    expect(screen.getByText('Promo agricole')).toBeInTheDocument()
    expect(mocks.campagnesList).toHaveBeenCalledTimes(1)
  })

  it('cliquer une ligne navigue vers le détail de la campagne', async () => {
    renderScreen()
    const row = await screen.findByText('Relance été')
    fireEvent.click(row.closest('tr'))
    expect(mocks.navigate).toHaveBeenCalledWith('/marketing/campagnes/1')
  })

  it('« Nouvelle campagne » ouvre le formulaire, la sauvegarde recharge la liste', async () => {
    mocks.campagnesCreate.mockResolvedValue({ data: {} })
    renderScreen()
    await screen.findByText('Relance été')
    fireEvent.click(screen.getByTestId('campagnes-nouvelle'))
    expect(screen.getByTestId('campagne-form')).toBeInTheDocument()
    fireEvent.change(screen.getByTestId('campagne-nom'), { target: { value: 'Nouvelle' } })
    fireEvent.click(screen.getByTestId('campagne-save'))
    await waitFor(() => expect(mocks.campagnesCreate).toHaveBeenCalled())
    await waitFor(() => expect(mocks.campagnesList).toHaveBeenCalledTimes(2))
  })
})
