import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gestionProjetApi from '../../../api/gestionProjetApi'
import PortefeuillePage from './PortefeuillePage'

/* AUDV16 (PROJ36/PROJ26) — écran Portefeuille : `tableau_portefeuille` était
   déjà câblé backend + client API mais aucun écran ne l'appelait. */

const PORTEFEUILLE = {
  nb_projets: 2,
  total_marge_reelle: '-1500.00',
  total_charge: '20',
  total_retards: 2,
  total_risques: 1,
  note_satisfaction_moyenne: 4.5,
  projets: [
    {
      projet_id: 10, code: 'P-1', nom: 'Villa Fès', statut: 'en_cours',
      avancement_pct: 40, nb_retards: 2, nb_risques: 1,
      marge_reelle: '-1500.00', charge_totale: '10',
      derniere_sante: 'orange', note_satisfaction: 4.5,
      politique_facturation: 'forfait',
    },
    {
      projet_id: 11, code: 'P-2', nom: 'Riad Marrakech', statut: 'planifie',
      avancement_pct: 0, nb_retards: 0, nb_risques: 0,
      marge_reelle: '0.00', charge_totale: '10',
      derniere_sante: null, note_satisfaction: null,
      politique_facturation: 'forfait',
    },
  ],
}

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getPortefeuille: vi.fn(() => Promise.resolve({ data: PORTEFEUILLE })),
  },
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('PortefeuillePage', () => {
  it('charge et affiche le tableau de bord portefeuille (lignes + totaux)', async () => {
    withProviders(<PortefeuillePage />)

    await waitFor(() => expect(gestionProjetApi.getPortefeuille).toHaveBeenCalled())
    // DataTable rend un double affichage (table desktop + cartes mobile) :
    // au moins une occurrence de chaque ligne, jamais une occurrence unique.
    await waitFor(() => expect(screen.getAllByText('Villa Fès').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Riad Marrakech').length).toBeGreaterThan(0)

    // Totaux portefeuille (bandeau KPI).
    const totalRetards = screen.getByText('Retards cumulés').closest('div')
    expect(within(totalRetards).getByText('2')).toBeInTheDocument()
  })

  it('re-filtre par statut', async () => {
    const user = userEvent.setup()
    withProviders(<PortefeuillePage />)
    await waitFor(() => expect(gestionProjetApi.getPortefeuille).toHaveBeenCalledTimes(1))

    const planifie = screen.getByRole('radio', { name: /Planifié/i })
    await user.click(planifie)

    await waitFor(() => expect(gestionProjetApi.getPortefeuille).toHaveBeenCalledTimes(2))
    expect(gestionProjetApi.getPortefeuille).toHaveBeenLastCalledWith({ statut: 'planifie' })
  })
})
