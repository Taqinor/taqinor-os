import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// Aucun réseau : le stub se COMPORTE comme axios (il renvoie une promesse).
const { post, navigate } = vi.hoisted(() => ({
  post: vi.fn(() => Promise.resolve({ data: {} })),
  navigate: vi.fn(),
}))
vi.mock('../api/axios', () => ({ default: { post, get: vi.fn(() => Promise.resolve({ data: {} })) } }))
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => navigate,
}))

import RegisterCompany from './RegisterCompany'

function afficher() {
  return render(
    <MemoryRouter>
      <RegisterCompany />
    </MemoryRouter>,
  )
}

function remplir({ societe = 'Taqinor Énergies', utilisateur = 'r.kasri',
                   motDePasse = 'MotDePasse!2026', email = '' } = {}) {
  fireEvent.change(screen.getByLabelText(/Nom de la société/i),
                   { target: { value: societe } })
  fireEvent.change(screen.getByLabelText(/Nom d'utilisateur du Directeur/i),
                   { target: { value: utilisateur } })
  fireEvent.change(screen.getByLabelText(/Adresse e-mail/i),
                   { target: { value: email } })
  fireEvent.change(screen.getByLabelText(/^Mot de passe$/i),
                   { target: { value: motDePasse } })
}

function soumettre() {
  fireEvent.click(screen.getByRole('button', { name: /Créer la société/i }))
}

/* PACT116 — le backend `POST /auth/register-company/` créait déjà société +
   profil + rôles système + compte Directeur ; il n'avait AUCUNE porte. Ces
   tests verrouillent les trois clauses du contrat : l'inscription part bien
   vers CET endpoint, les 400 par champ du serveur sont affichés TELS QUELS, et
   aucune règle d'unicité n'est rejouée côté client. */
describe('RegisterCompany (PACT116)', () => {
  beforeEach(() => {
    post.mockReset()
    post.mockResolvedValue({ data: { company_id: 3, username: 'r.kasri' } })
    navigate.mockReset()
  })
  afterEach(cleanup)

  it('poste vers /auth/register-company/ avec les champs saisis', async () => {
    afficher()
    remplir({ email: 'reda@taqinor.ma' })
    soumettre()

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(post).toHaveBeenCalledWith('/auth/register-company/', {
      company_nom: 'Taqinor Énergies',
      username: 'r.kasri',
      email: 'reda@taqinor.ma',
      password: 'MotDePasse!2026',
    })
  })

  it('renvoie vers la connexion quand la société est créée', async () => {
    afficher()
    remplir()
    soumettre()

    await waitFor(() => expect(navigate).toHaveBeenCalledWith(
      '/login?inscription=ok', { replace: true }))
  })

  it('affiche TELLE QUELLE l’erreur 400 par champ renvoyée par le serveur', async () => {
    post.mockRejectedValue({
      response: {
        status: 400,
        data: { username: ["Ce nom d'utilisateur est deja utilise."] },
      },
    })
    afficher()
    remplir()
    soumettre()

    expect(await screen.findByText("Ce nom d'utilisateur est deja utilise."))
      .toBeInTheDocument()
    // Le message n'est pas reformulé : c'est la phrase du serveur, mot pour mot.
    expect(screen.getByLabelText(/Nom d'utilisateur du Directeur/i))
      .toHaveAttribute('aria-invalid', 'true')
    expect(navigate).not.toHaveBeenCalled()
  })

  it('affiche plusieurs champs en erreur en même temps', async () => {
    post.mockRejectedValue({
      response: {
        status: 400,
        data: {
          company_nom: ['Ce champ est requis.'],
          password: ['Ce champ est requis.'],
        },
      },
    })
    afficher()
    soumettre()

    await waitFor(() => expect(screen.getAllByText('Ce champ est requis.'))
      .toHaveLength(2))
  })

  it('ne duplique AUCUNE règle d’unicité côté client : le serveur tranche seul',
    async () => {
      // Un nom d'utilisateur déjà pris n'est PAS devinable côté écran : la
      // soumission part quand même, et c'est le 400 du serveur qui informe.
      afficher()
      remplir({ utilisateur: 'admin' })
      soumettre()

      await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
      expect(screen.queryByText(/déjà pris|deja pris|déjà utilisé/i)).toBeNull()
    })

  it('signale une panne réseau sans jargon ni JSON brut', async () => {
    post.mockRejectedValue(new Error('Network Error'))
    afficher()
    remplir()
    soumettre()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Impossible de contacter le serveur/i)
  })

  it('offre un retour vers la connexion', () => {
    afficher()
    expect(screen.getByRole('link', { name: /Se connecter/i }))
      .toHaveAttribute('href', '/login')
  })
})
