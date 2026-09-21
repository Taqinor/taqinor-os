import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT53 — Done : « une note ajoutée à une soumission apparaît dans son fil
   avec son auteur et son horodatage ». On vérifie donc, en plus du rendu de
   la liste, que la note publiée revient DANS le fil avec l'auteur posé par le
   serveur — jamais un auteur deviné côté client. */

const getSoumissions = vi.fn()
const getHistorique = vi.fn()
const noter = vi.fn()
const getDepartements = vi.fn()
const getCycles = vi.fn()

vi.mock('../../api/fpaApi', () => ({
  default: {
    getSoumissions: (...a) => getSoumissions(...a),
    getSoumissionHistorique: (...a) => getHistorique(...a),
    noterSoumission: (...a) => noter(...a),
    getDepartements: (...a) => getDepartements(...a),
    getCycles: (...a) => getCycles(...a),
  },
}))

import SoumissionsBudgetPage from './SoumissionsBudgetPage'

const SOUMISSIONS = [
  {
    id: 3, cycle: 1, departement: 2, statut: 'soumis', motif_rejet: '',
    soumis_par: 9, soumis_le: '2026-08-01T09:00:00Z',
    valide_par: null, valide_le: null,
  },
  {
    id: 4, cycle: 1, departement: 5, statut: 'rejete',
    motif_rejet: 'Masse salariale hors cadrage', soumis_par: 9,
    soumis_le: '2026-08-01T09:00:00Z', valide_par: 1,
    valide_le: '2026-08-02T09:00:00Z',
  },
]

function monter() {
  return render(
    <MemoryRouter>
      <ThemeProvider><SoumissionsBudgetPage /></ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  getSoumissions.mockResolvedValue({ data: { results: SOUMISSIONS } })
  getDepartements.mockResolvedValue({
    data: [{ id: 2, nom: 'Commercial' }, { id: 5, nom: 'Technique' }],
  })
  getCycles.mockResolvedValue({ data: [{ id: 1, nom: 'Budget 2026' }] })
  getHistorique.mockResolvedValue({
    data: [{
      id: 100, kind: 'modification', field: 'statut', field_label: 'Statut',
      old_value: 'en_saisie', new_value: 'soumis', body: '',
      user_username: 'meryem', created_at: '2026-08-01T09:00:00Z',
    }],
  })
  noter.mockResolvedValue({
    data: {
      id: 101, kind: 'note', field: '', field_label: '', old_value: '',
      new_value: '', body: 'Budget revu avec la direction.',
      user_username: 'reda', created_at: '2026-08-03T10:30:00Z',
    },
  })
})

describe('SoumissionsBudgetPage (PACT53)', () => {
  it('liste les soumissions avec département, cycle et statut lisible', async () => {
    monter()
    const liste = await screen.findByTestId('fpa-soum-liste')
    await waitFor(() => expect(within(liste).getByText('Commercial')).toBeTruthy())
    await waitFor(() => expect(within(liste).getAllByText('Budget 2026').length).toBe(2))
    expect(within(liste).getByText('Technique')).toBeTruthy()
    expect(within(liste).getByText('Soumis')).toBeTruthy()
    expect(within(liste).getByText('Rejeté')).toBeTruthy()
    expect(within(liste).getByText('Masse salariale hors cadrage')).toBeTruthy()
  })

  it("ouvre le fil d'une soumission et affiche ses entrées existantes", async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('fpa-soum-liste')
    await user.click(screen.getByTestId('fpa-soum-ouvrir-3'))

    await waitFor(() => expect(getHistorique).toHaveBeenCalledWith(3))
    const fil = await screen.findByTestId('fpa-soum-fil')
    // L'auteur du log automatique vient du serveur.
    expect(within(fil).getAllByText(/meryem/).length).toBeGreaterThan(0)
  })

  it('publie une note qui apparaît dans le fil avec son auteur (Done PACT53)', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('fpa-soum-liste')
    await user.click(screen.getByTestId('fpa-soum-ouvrir-3'))
    await screen.findByTestId('fpa-soum-fil')

    await user.type(
      screen.getByLabelText('Nouvelle note'), 'Budget revu avec la direction.',
    )
    await user.click(screen.getByTestId('fpa-soum-noter'))

    await waitFor(() => expect(noter).toHaveBeenCalledWith(
      3, 'Budget revu avec la direction.',
    ))
    const fil = await screen.findByTestId('fpa-soum-fil')
    expect(within(fil).getByText(/Budget revu avec la direction\./)).toBeTruthy()
    // Auteur SERVEUR rendu dans le fil (jamais deviné côté client).
    expect(within(fil).getAllByText(/reda/).length).toBeGreaterThan(0)
  })

  it("n'appelle pas le serveur pour une note vide", async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('fpa-soum-liste')
    await user.click(screen.getByTestId('fpa-soum-ouvrir-3'))
    await screen.findByTestId('fpa-soum-fil')
    await user.click(screen.getByTestId('fpa-soum-noter'))
    expect(noter).not.toHaveBeenCalled()
  })

  it('dégrade proprement quand les soumissions sont indisponibles', async () => {
    getSoumissions.mockRejectedValue({ response: { data: { detail: 'Service KO.' } } })
    monter()
    expect(await screen.findByText('Service KO.')).toBeTruthy()
  })
})
