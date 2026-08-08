import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import VehiculesPermis from './VehiculesPermis.jsx'

/* PACT81 — Affectation véhicule & permis de conduire. Le refus serveur (permis
   absent/expiré, FG198) doit s'afficher TEL QUEL — jamais un filtrage côté
   client. */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getPermisConduire: vi.fn(empty),
      getAffectationsVehicule: vi.fn(empty),
      getEmployes: vi.fn(() => Promise.resolve({ data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }] })),
      createPermisConduire: vi.fn(),
      createAffectationVehicule: vi.fn(),
      terminerAffectationVehicule: vi.fn(),
    },
  }
})

vi.mock('../../api/flotteApi', () => ({
  default: {
    vehicules: {
      list: vi.fn(() => Promise.resolve({ data: [{ id: 3, immatriculation: '12345-A-6', marque: 'Renault', modele: 'Kangoo' }] })),
    },
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <VehiculesPermis />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('VehiculesPermis (PACT81)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module et propose les deux vues', async () => {
    renderScreen()
    expect(await screen.findByText('Véhicules & permis')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Permis de conduire' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Affectations véhicule' })).toBeInTheDocument()
  })

  it('crée un permis via rhApi.createPermisConduire', async () => {
    rhApi.createPermisConduire.mockResolvedValueOnce({ data: { id: 1 } })
    renderScreen()
    await screen.findByText('Véhicules & permis')

    fireEvent.click(await screen.findByRole('button', { name: /Nouveau permis/ }))
    fireEvent.change(screen.getByLabelText('Conducteur'), { target: { value: '9' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(rhApi.createPermisConduire).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9', categorie: 'B' }),
    ))
  })

  it('affiche le refus serveur tel quel quand l’affectation est refusée (permis invalide)', async () => {
    rhApi.createAffectationVehicule.mockRejectedValueOnce({
      response: { data: { employe: ["Affectation refusée : ce conducteur n'a pas de permis de conduire valide (FG197)."] } },
    })
    renderScreen()
    await screen.findByText('Véhicules & permis')
    fireEvent.click(screen.getByRole('radio', { name: 'Affectations véhicule' }))

    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle affectation/ }))
    fireEvent.change(screen.getByLabelText('Conducteur'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('Véhicule'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Date de début'), { target: { value: '2026-08-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(await screen.findByText(/Affectation refusée : ce conducteur n'a pas de permis/)).toBeInTheDocument()
  })
})
