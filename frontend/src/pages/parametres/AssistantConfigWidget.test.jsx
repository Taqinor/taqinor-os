import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* PACT145 — Assistant de paramétrage (NTAI35) : `POST /ai/assistant-config/`
   existait sans aucun appelant frontend. Le point clé prouvé ici : la réponse
   contient TOUJOURS un lien cliquable — avec clé LLM (`source: 'llm'`) comme
   sans (`source: 'faq'`, repli statique). */

const { post } = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { post } }))

import AssistantConfigWidget from './AssistantConfigWidget'

const REPONSE_LLM = {
  question: 'où régler la TVA ?',
  reponse: 'Le taux de TVA par défaut se règle dans Paramètres → Entreprise.',
  ecrans: [{
    titre: "Paramètres de l'entreprise", lien: '/parametres',
    resume: 'TVA, ICE, RIB, logo…',
  }],
  source: 'llm',
  modifie: false,
}

const REPONSE_FAQ = { ...REPONSE_LLM, source: 'faq' }

afterEach(() => { cleanup(); vi.clearAllMocks() })

function afficher() {
  return render(<MemoryRouter><AssistantConfigWidget /></MemoryRouter>)
}

async function poser(user, texte) {
  await user.type(screen.getByLabelText('Où régler… ?'), texte)
  await user.click(screen.getByRole('button', { name: /Demander/ }))
}

describe('AssistantConfigWidget (PACT145)', () => {
  it('renvoie une réponse et un lien cliquable vers le bon écran', async () => {
    const user = userEvent.setup()
    post.mockResolvedValue({ data: REPONSE_LLM })
    afficher()

    await poser(user, 'où régler la TVA ?')

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/ai/assistant-config/', { question: 'où régler la TVA ?' }))

    const bloc = await screen.findByTestId('assistant-config-reponse')
    expect(within(bloc).getByText(/Paramètres → Entreprise/)).toBeInTheDocument()

    const lien = screen.getByTestId('assistant-config-lien')
    expect(lien).toHaveAttribute('href', '/parametres')
    expect(within(lien).getByText("Paramètres de l'entreprise")).toBeInTheDocument()
  })

  it('donne toujours un lien quand aucune clé n\'est configurée (repli FAQ)', async () => {
    const user = userEvent.setup()
    post.mockResolvedValue({ data: REPONSE_FAQ })
    afficher()

    await poser(user, 'où régler la TVA ?')

    const lien = await screen.findByTestId('assistant-config-lien')
    expect(lien).toHaveAttribute('href', '/parametres')
    // Le repli est signalé, jamais présenté comme une panne.
    expect(screen.getByText('Réponse de référence')).toBeInTheDocument()
    expect(screen.queryByText(/indisponible/)).toBeNull()
  })

  it('une question vide n\'appelle jamais le serveur', async () => {
    const user = userEvent.setup()
    afficher()
    await user.click(screen.getByRole('button', { name: /Demander/ }))
    expect(post).not.toHaveBeenCalled()
  })

  it('affiche un message clair quand le service répond en erreur', async () => {
    const user = userEvent.setup()
    post.mockRejectedValue({ response: { data: { detail: 'Service indisponible.' } } })
    afficher()

    await poser(user, 'où régler la TVA ?')

    expect(await screen.findByText('Service indisponible.')).toBeInTheDocument()
    expect(screen.queryByTestId('assistant-config-reponse')).toBeNull()
  })
})
