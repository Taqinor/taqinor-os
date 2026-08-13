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
