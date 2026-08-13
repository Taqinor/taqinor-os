import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT122 — Done : l'écran liste les jeux de données RÉELS, permet de
   construire une requête simple, de l'exécuter et de la sauvegarder en
   personnel ou en société. On vérifie aussi l'honnêteté d'affichage : le
   nombre annoncé est celui du catalogue servi, jamais un chiffre décoratif. */

const datasets = vi.fn()
const listQueries = vi.fn()
const createQuery = vi.fn()
const removeQuery = vi.fn()
const runAdhoc = vi.fn()
const run = vi.fn()

vi.mock('../../api/coreApi', () => ({
  default: {
    savedQueries: {
      datasets: (...a) => datasets(...a),
      list: (...a) => listQueries(...a),
      create: (...a) => createQuery(...a),
      remove: (...a) => removeQuery(...a),
      runAdhoc: (...a) => runAdhoc(...a),
      run: (...a) => run(...a),
    },
  },
}))

import ExplorateurDonneesPage from './ExplorateurDonneesPage'

const CATALOGUE = [
  { name: 'sav_tickets', label: 'Tickets SAV', fields: ['id', 'statut', 'priorite'] },
]

function monter() {
  return render(
    <MemoryRouter>
      <ThemeProvider><ExplorateurDonneesPage /></ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  datasets.mockResolvedValue({ data: CATALOGUE })
  listQueries.mockResolvedValue({ data: [] })
  createQuery.mockResolvedValue({ data: { id: 1 } })
  removeQuery.mockResolvedValue({ data: {} })
  runAdhoc.mockResolvedValue({
    data: { rows: [{ statut: 'ouvert', count: 3 }, { statut: 'clos', count: 5 }] },
  })
  run.mockResolvedValue({ data: { rows: [{ statut: 'ouvert', count: 3 }] } })
})

describe('ExplorateurDonneesPage (PACT122)', () => {
  it('liste les jeux de données RÉELS et annonce leur nombre exact', async () => {
    monter()
    await waitFor(() => expect(datasets).toHaveBeenCalled())
    const liste = await screen.findByTestId('expl-datasets')
    expect(within(liste).getByRole('button', { name: 'Tickets SAV' })).toBeTruthy()
    // Honnêteté : un seul dataset enregistré → le compteur dit « 1 ».
    expect(screen.getByTestId('expl-nb-datasets')).toHaveTextContent('1 enregistré(s)')
  })

  it("annonce franchement un catalogue vide plutôt que d'inventer", async () => {
    datasets.mockResolvedValue({ data: [] })
    monter()
    await waitFor(() => expect(datasets).toHaveBeenCalled())
    expect(await screen.findByText('Aucun jeu de données')).toBeTruthy()
    expect(screen.getByTestId('expl-nb-datasets')).toHaveTextContent('0 enregistré(s)')
  })

  it('construit et exécute une requête simple, puis affiche les lignes', async () => {
    const user = userEvent.setup()
    monter()
    const liste = await screen.findByTestId('expl-datasets')
    await user.click(within(liste).getByRole('button', { name: 'Tickets SAV' }))

    await screen.findByTestId('expl-constructeur')
    await user.click(screen.getByLabelText('Champ statut'))
    await user.click(screen.getByTestId('expl-executer'))

    await waitFor(() => expect(runAdhoc).toHaveBeenCalledWith('sav_tickets', {
      select: ['statut'], limit: 50,
    }))
    const resultat = await screen.findByTestId('expl-resultat')
    expect(within(resultat).getByText('ouvert')).toBeTruthy()
    expect(within(resultat).getByText('clos')).toBeTruthy()
  })

  it('sauvegarde la requête en PERSONNEL par défaut', async () => {
    const user = userEvent.setup()
    monter()
    const liste = await screen.findByTestId('expl-datasets')
    await user.click(within(liste).getByRole('button', { name: 'Tickets SAV' }))
    await screen.findByTestId('expl-constructeur')

    await user.type(screen.getByLabelText('Titre de la requête'), 'Tickets par statut')
    await user.click(screen.getByTestId('expl-sauvegarder'))

    await waitFor(() => expect(createQuery).toHaveBeenCalledWith({
      titre: 'Tickets par statut',
      dataset: 'sav_tickets',
      spec: { limit: 50 },
      partage: false,
    }))
  })

  it('sauvegarde la requête en SOCIÉTÉ quand le partage est coché', async () => {
    const user = userEvent.setup()
    monter()
    const liste = await screen.findByTestId('expl-datasets')
    await user.click(within(liste).getByRole('button', { name: 'Tickets SAV' }))
    await screen.findByTestId('expl-constructeur')

    await user.type(screen.getByLabelText('Titre de la requête'), 'Tickets société')
    await user.click(screen.getByLabelText('Partager avec la société'))
    await user.click(screen.getByTestId('expl-sauvegarder'))

    await waitFor(() => expect(createQuery).toHaveBeenCalledWith(
      expect.objectContaining({ titre: 'Tickets société', partage: true }),
    ))
  })

  it('refuse de sauvegarder sans titre (aucun appel serveur)', async () => {
    const user = userEvent.setup()
    monter()
    const liste = await screen.findByTestId('expl-datasets')
    await user.click(within(liste).getByRole('button', { name: 'Tickets SAV' }))
    await screen.findByTestId('expl-constructeur')
    await user.click(screen.getByTestId('expl-sauvegarder'))
    expect(createQuery).not.toHaveBeenCalled()
  })

  it('exécute une requête déjà sauvegardée', async () => {
    listQueries.mockResolvedValue({
      data: [{ id: 12, titre: 'Tickets ouverts', dataset: 'sav_tickets', partage: true }],
    })
    const user = userEvent.setup()
    monter()
    await screen.findByTestId('expl-sauvegardees')
    await user.click(screen.getByTestId('expl-run-12'))
    await waitFor(() => expect(run).toHaveBeenCalledWith(12))
    expect(await screen.findByTestId('expl-resultat')).toBeTruthy()
  })

  it('dégrade proprement quand le catalogue est indisponible', async () => {
    datasets.mockRejectedValue({ response: { data: { detail: 'Catalogue KO.' } } })
    monter()
    expect(await screen.findByText('Catalogue KO.')).toBeTruthy()
  })
})
