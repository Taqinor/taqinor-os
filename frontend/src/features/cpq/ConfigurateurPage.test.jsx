import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT125 — l'écran « Configurateur guidé » couvre le parcours backend
   NTCPQ9/10 de bout en bout : démarrer une session, répondre aux questions
   ACTIVES, afficher le résultat résolu, générer un devis BROUILLON, et gérer
   les questions depuis l'onglet du même écran. Tout le câblage réseau est
   mocké : ces tests vérifient le parcours et les CORPS envoyés, jamais le
   serveur. */

const demarrer = vi.fn()
const repondre = vi.fn()
const resultat = vi.fn()
const genererDevis = vi.fn()
const getQuestions = vi.fn()
const createQuestion = vi.fn()
const updateQuestion = vi.fn()
const deleteQuestion = vi.fn()
const getClients = vi.fn()

vi.mock('../../api/cpqApi', () => ({
  default: {
    demarrerConfigurateur: (...a) => demarrer(...a),
    repondreConfigurateur: (...a) => repondre(...a),
    resultatConfigurateur: (...a) => resultat(...a),
    genererDevisConfigurateur: (...a) => genererDevis(...a),
    getQuestionsConfigurateur: (...a) => getQuestions(...a),
    createQuestionConfigurateur: (...a) => createQuestion(...a),
    updateQuestionConfigurateur: (...a) => updateQuestion(...a),
    deleteQuestionConfigurateur: (...a) => deleteQuestion(...a),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: { getClients: (...a) => getClients(...a) },
}))

import ConfigurateurPage from './ConfigurateurPage'

const QUESTIONS = [
  {
    id: 7,
    ordre: 1,
    texte: 'Puissance souhaitée (kWc)',
    type: 'NUMERIQUE',
    options: { champ: 'kwc' },
    actif: true,
    champ: 'kwc',
  },
  {
    id: 8,
    ordre: 2,
    texte: 'Type de toiture',
    type: 'CHOIX_UNIQUE',
    options: { champ: 'toiture', choices: ['Tôle', 'Béton'] },
    actif: true,
    champ: 'toiture',
  },
]

function monter() {
  return render(
    <MemoryRouter>
      <ThemeProvider><ConfigurateurPage /></ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  demarrer.mockResolvedValue({ data: { session: 'tok-1', questions: QUESTIONS } })
  repondre.mockResolvedValue({ data: { detail: 'Réponses enregistrées.' } })
  resultat.mockResolvedValue({
    data: {
      context: { kwc: 12, toiture: 'Tôle' },
      actions_declenchees: [
        { regle_id: 3, nom: 'Kit 12 kWc', actions: [{ produit_id: 42, quantite: 2 }] },
      ],
    },
  })
  genererDevis.mockResolvedValue({ data: { devis_id: 99, reference: 'DEV-2026-0007' } })
  getQuestions.mockResolvedValue({ data: { results: QUESTIONS } })
  createQuestion.mockResolvedValue({ data: { id: 9 } })
  updateQuestion.mockResolvedValue({ data: { id: 8 } })
  deleteQuestion.mockResolvedValue({ data: {} })
  getClients.mockResolvedValue({ data: { results: [{ id: 5, nom: 'SunRak' }] } })
})

describe('ConfigurateurPage (PACT125)', () => {
  it('monte les deux onglets du même écran (configurateur + questions)', () => {
    monter()
    expect(screen.getByRole('tab', { name: 'Configurateur' })).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Questions' })).toBeTruthy()
  })

  it('démarre une session et affiche les questions actives', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByTestId('cpq-cfg-demarrer'))
    await waitFor(() => expect(demarrer).toHaveBeenCalled())
    expect(await screen.findByText('Puissance souhaitée (kWc)')).toBeTruthy()
    expect(screen.getByText('Type de toiture')).toBeTruthy()
  })

  it('envoie les réponses (numérique en NOMBRE) puis affiche le résultat résolu', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByTestId('cpq-cfg-demarrer'))
    await screen.findByText('Puissance souhaitée (kWc)')

    await user.type(screen.getByLabelText('Puissance souhaitée (kWc)'), '12')
    await user.click(screen.getByRole('button', { name: 'Tôle' }))
    await user.click(screen.getByTestId('cpq-cfg-resoudre'))

    await waitFor(() => expect(repondre).toHaveBeenCalled())
    expect(repondre).toHaveBeenCalledWith('tok-1', [
      { question: 7, valeur: 12 },
      { question: 8, valeur: 'Tôle' },
    ])
    await waitFor(() => expect(resultat).toHaveBeenCalledWith('tok-1'))
    // Le résultat résolu est affiché (produit + quantité issus des règles).
    expect(await screen.findByTestId('cpq-cfg-resolus')).toBeTruthy()
    expect(screen.getByText('#42')).toBeTruthy()
  })

  it('génère un devis brouillon pour le client choisi (Done PACT125)', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByTestId('cpq-cfg-demarrer'))
    await screen.findByText('Puissance souhaitée (kWc)')
    await user.click(screen.getByTestId('cpq-cfg-resoudre'))
    await screen.findByTestId('cpq-cfg-resultat')

    // Tant qu'aucun client n'est choisi le bouton reste inerte : le serveur
    // refuserait la génération (« Un client ou un lead est requis »).
    expect(screen.getByTestId('cpq-cfg-generer-devis')).toBeDisabled()

    await user.click(screen.getByLabelText('Client du devis'))
    await user.click(await screen.findByText('SunRak'))
    await user.click(screen.getByTestId('cpq-cfg-generer-devis'))

    await waitFor(() => expect(genererDevis).toHaveBeenCalledWith('tok-1', { client: '5' }))
    expect(await screen.findByTestId('cpq-cfg-devis-cree')).toHaveTextContent('DEV-2026-0007')
  })

  it('ne jette pas quand le démarrage échoue (session absente)', async () => {
    demarrer.mockRejectedValue({ response: { data: { detail: 'Indisponible.' } } })
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByTestId('cpq-cfg-demarrer'))
    await waitFor(() => expect(demarrer).toHaveBeenCalled())
    expect(screen.getByText('Aucune session en cours')).toBeTruthy()
  })

  it("l'onglet Questions liste les questions et en ajoute une (options normalisées)", async () => {
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByRole('tab', { name: 'Questions' }))
    await waitFor(() => expect(getQuestions).toHaveBeenCalled())
    expect(await screen.findByTestId('cpq-q-liste')).toBeTruthy()

    await user.type(screen.getByLabelText('Texte de la question'), 'Batterie ?')
    await user.type(screen.getByLabelText('Clé de contexte'), 'batterie')
    await user.type(screen.getByLabelText('Choix proposés'), 'Oui, Non')
    await user.click(screen.getByTestId('cpq-q-creer'))

    await waitFor(() => expect(createQuestion).toHaveBeenCalledWith({
      texte: 'Batterie ?',
      type: 'CHOIX_UNIQUE',
      ordre: 0,
      options: { champ: 'batterie', choices: ['Oui', 'Non'] },
      actif: true,
    }))
  })

  it("l'onglet Questions dégrade proprement quand la liste est indisponible", async () => {
    getQuestions.mockRejectedValue({ response: { data: { detail: 'Boum.' } } })
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByRole('tab', { name: 'Questions' }))
    await waitFor(() => expect(getQuestions).toHaveBeenCalled())
    expect(await screen.findByText('Boum.')).toBeTruthy()
  })
})
