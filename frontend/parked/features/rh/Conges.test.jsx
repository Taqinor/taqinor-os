import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import Conges from './Conges.jsx'

/* ZRH3 — l'écran congés expose le rapport annuel `/rh/demandes-conge/rapport/`
   (par type ET par employé). Les clés viennent du sélecteur serveur
   `selectors.rapport_conges` : par_type[{code, libelle, jours}] et
   par_employe[{nom, jours, solde_disponible}] — jamais inventées ici. */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getDemandesConge: vi.fn(empty),
      getSoldesConge: vi.fn(empty),
      getCalendrierConges: vi.fn(empty),
      getRapportConges: vi.fn(() => Promise.resolve({ data: { par_type: [], par_employe: [] } })),
      validerDemandeConge: vi.fn(),
      refuserDemandeConge: vi.fn(),
    },
  }
})

function renderConges() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Conges />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Conges — rapport annuel (ZRH3)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('charge le rapport et affiche les deux tableaux', async () => {
    rhApi.getRapportConges.mockResolvedValueOnce({
      data: {
        par_type: [{ type_absence_id: 3, code: 'CP', libelle: 'Congé payé', jours: '12.0' }],
        par_employe: [{ employe_id: 9, nom: 'Bennani Youssef', jours: '12.0', solde_disponible: '6.0' }],
      },
    })
    renderConges()
    await screen.findAllByText('Congés & absences')

    fireEvent.click(screen.getByRole('radio', { name: 'Rapport' }))
    expect((await screen.findAllByText('Congé payé')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Bennani Youssef').length).toBeGreaterThan(0)
    expect(rhApi.getRapportConges).toHaveBeenCalled()
  })
})

/* AUDV20 — la fiche solde affiche le DROIT LÉGAL annuel théorique
   (`droit_annuel`, servi par SoldeCongeSerializer depuis
   services.droit_annuel). Clé du serveur, jamais inventée ici. */
describe('Conges — droit annuel théorique sur la fiche solde (AUDV20)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('affiche le droit annuel quand le serveur le renvoie', async () => {
    rhApi.getSoldesConge.mockResolvedValueOnce({
      data: [{
        id: 1, employe: 9, annee: 2026, acquis: '9.00', report: '0.00',
        pris: '2.00', disponible: '7.00', droit_annuel: '19.50',
      }],
    })
    renderConges()
    await screen.findAllByText('Congés & absences')

    fireEvent.click(screen.getByRole('radio', { name: 'Soldes' }))
    expect(await screen.findByText(/Droit annuel théorique/)).toBeTruthy()
    expect(screen.getByText(/19,5/)).toBeTruthy()
  })

  it('n’affiche aucun droit annuel si le serveur ne le calcule pas', async () => {
    rhApi.getSoldesConge.mockResolvedValueOnce({
      data: [{
        id: 2, employe: 10, annee: 2026, acquis: '3.00', report: '0.00',
        pris: '0.00', disponible: '3.00', droit_annuel: null,
      }],
    })
    renderConges()
    await screen.findAllByText('Congés & absences')

    fireEvent.click(screen.getByRole('radio', { name: 'Soldes' }))
    await screen.findByText(/acquis/)
    expect(screen.queryByText(/Droit annuel théorique/)).toBeNull()
  })
})
