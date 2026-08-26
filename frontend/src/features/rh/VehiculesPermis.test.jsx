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
      // WIR241 — bandeau + badge des permis expirant sous 30 jours.
      getPermisExpirantBientot: vi.fn(empty),
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
    expect((await screen.findAllByText('Véhicules & permis')).length).toBeGreaterThan(0)
    expect(screen.getByRole('radio', { name: 'Permis de conduire' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Affectations véhicule' })).toBeInTheDocument()
  })

  it('crée un permis via rhApi.createPermisConduire', async () => {
    rhApi.createPermisConduire.mockResolvedValueOnce({ data: { id: 1 } })
    renderScreen()
    await screen.findAllByText('Véhicules & permis')

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouveau permis/ }))[0])
    fireEvent.change(screen.getByLabelText('Conducteur'), { target: { value: '9' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Enregistrer' })[0])

    await waitFor(() => expect(rhApi.createPermisConduire).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9', categorie: 'B' }),
    ))
  })

  it('affiche le refus serveur tel quel quand l’affectation est refusée (permis invalide)', async () => {
    rhApi.createAffectationVehicule.mockRejectedValueOnce({
      response: { data: { employe: ["Affectation refusée : ce conducteur n'a pas de permis de conduire valide (FG197)."] } },
    })
    renderScreen()
    await screen.findAllByText('Véhicules & permis')
    fireEvent.click(screen.getByRole('radio', { name: 'Affectations véhicule' }))

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle affectation/ }))[0])
    fireEvent.change(screen.getByLabelText('Conducteur'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('Véhicule'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Date de début'), { target: { value: '2026-08-01' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Enregistrer' })[0])

    expect((await screen.findAllByText(/Affectation refusée : ce conducteur n'a pas de permis/)).length).toBeGreaterThan(0)
  })

  it('WIR241 — bandeau + badge des permis expirant sous 30 jours (rapprochement par id)', async () => {
    rhApi.getPermisConduire.mockResolvedValueOnce({
      data: [{
        id: 4, employe: 9, employe_nom: 'Bennani Youssef', categorie: 'B',
        categorie_display: 'B — Véhicules légers', numero: 'P123',
        date_expiration: '2026-09-01', valide: true,
      }],
    })
    rhApi.getPermisExpirantBientot.mockResolvedValueOnce({
      data: [{ id: 4, employe: 9, employe_nom: 'Bennani Youssef', date_expiration: '2026-09-01', valide: true }],
    })
    renderScreen()
    await screen.findAllByText('Véhicules & permis')

    expect(await screen.findByText(/1 permis expirant sous 30 jours/)).toBeInTheDocument()
    expect((await screen.findAllByText('Expire bientôt')).length).toBeGreaterThan(0)
  })
})
