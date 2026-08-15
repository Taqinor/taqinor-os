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
      // WIR241 — permis expirant sous 30 jours (bandeau + badge de ligne).
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
})

/* WIR241 — un permis à échéance ne se voyait qu'une fois DÉJÀ expiré (donc
   après un refus d'affectation serveur). Le rapprochement se fait par ID. */
describe('VehiculesPermis — WIR241 : permis expirant bientôt', () => {
  const PERMIS = {
    id: 15, employe: 9, employe_nom: 'Bennani Youssef',
    categorie: 'B', categorie_display: 'B — Véhicules légers',
    numero: 'AB12345', date_expiration: '2026-09-01', valide: true,
  }

  beforeEach(() => vi.clearAllMocks())

  it('affiche le bandeau 30 jours et le badge « Expire bientôt » sur la ligne', async () => {
    rhApi.getPermisConduire.mockResolvedValueOnce({ data: [PERMIS] })
    rhApi.getPermisExpirantBientot.mockResolvedValueOnce({ data: [PERMIS] })
    renderScreen()
    await screen.findAllByText('Véhicules & permis')

    expect(await screen.findByText(/1 permis expire\(nt\) dans les 30 prochains jours/))
      .toBeInTheDocument()
    expect((await screen.findAllByText('Expire bientôt'))[0]).toBeInTheDocument()
  })

  it('un permis valide hors fenêtre reste « Valide »', async () => {
    rhApi.getPermisConduire.mockResolvedValueOnce({ data: [PERMIS] })
    rhApi.getPermisExpirantBientot.mockResolvedValueOnce({ data: [] })
    renderScreen()
    await screen.findAllByText('Véhicules & permis')

    expect((await screen.findAllByText('Valide'))[0]).toBeInTheDocument()
    expect(screen.queryByText('Expire bientôt')).toBeNull()
  })
})
