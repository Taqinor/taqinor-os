import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* PACT117 — Onglet « Modèles brandés » : `core.BrandedTemplate` (FG393) avait
   un ViewSet exposé et AUCUN appelant frontend. Ces tests prouvent que l'écran
   liste, crée et prévisualise (action serveur `preview/`). */

const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn(),
}))
vi.mock('../../api/axios', () => ({
  default: { get, post, patch, delete: del },
}))

import ModelesBrandesSection from './ModelesBrandesSection'

const MODELES = [
  {
    id: 7, kind: 'email', code: 'relance_devis', nom: 'Relance de devis',
    sujet: 'Votre devis {{ devis.numero }}', corps: 'Bonjour {{ client.nom }},',
    actif: true, variables: ['devis.numero', 'client.nom'],
  },
  {
    id: 8, kind: 'whatsapp', code: 'rdv', nom: 'Confirmation de RDV',
    sujet: '', corps: 'RDV le {{ rdv.date }}', actif: false, variables: ['rdv.date'],
  },
]

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderAvecRole(role) {
  const store = configureStore({ reducer: { auth: (state = { role }) => state } })
  return render(<Provider store={store}><ModelesBrandesSection /></Provider>)
}

describe('ModelesBrandesSection (PACT117)', () => {
  it('liste les modèles de la société groupés par canal', async () => {
    get.mockResolvedValue({ data: MODELES })
    renderAvecRole('admin')

    expect(get).toHaveBeenCalledWith('/core/branded-templates/')
    const ligne = await screen.findByTestId('modele-brande-email-relance_devis')
    expect(within(ligne).getByText('Relance de devis')).toBeInTheDocument()
    expect(within(ligne).getByText('relance_devis')).toBeInTheDocument()

    const autre = screen.getByTestId('modele-brande-whatsapp-rdv')
    expect(within(autre).getByText('Inactif')).toBeInTheDocument()
    // Les deux canaux présents sont rendus comme en-têtes de groupe (et le
    // canal PDF, sans modèle, n'apparaît pas).
    expect(screen.getByTestId('groupe-canal-email')).toBeInTheDocument()
    expect(screen.getByTestId('groupe-canal-whatsapp')).toBeInTheDocument()
    expect(screen.queryByTestId('groupe-canal-pdf')).toBeNull()
  })

  it('crée un modèle email « relance_devis » sans jamais envoyer company', async () => {
    const user = userEvent.setup()
    get.mockResolvedValue({ data: [] })
    post.mockResolvedValue({ data: { ...MODELES[0], id: 42 } })
    renderAvecRole('admin')
    await screen.findByText('Aucun modèle brandé')

    await user.type(screen.getByPlaceholderText("Code d'usage (ex. relance_devis)"), 'relance_devis')
    await user.type(screen.getByPlaceholderText('Nom (ex. Relance de devis)'), 'Relance de devis')
    await user.click(screen.getByRole('button', { name: /Créer le modèle/ }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/core/branded-templates/', {
      kind: 'email', code: 'relance_devis', nom: 'Relance de devis',
      sujet: '', corps: '',
    }))
    // `company` n'est jamais dans le corps (imposée côté serveur).
    expect(Object.keys(post.mock.calls[0][1])).not.toContain('company')
  })

  it("affiche l'aperçu rendu sur le contexte d'exemple", async () => {
    const user = userEvent.setup()
    get.mockResolvedValue({ data: MODELES })
    post.mockResolvedValue({
      data: { sujet: 'Votre devis DEV-2026-0042', corps: 'Bonjour SARL Exemple,' },
    })
    renderAvecRole('admin')

    const ligne = await screen.findByTestId('modele-brande-email-relance_devis')
    await user.click(within(ligne).getByRole('button', { name: /Aperçu/ }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/core/branded-templates/7/preview/',
      { context: expect.objectContaining({ client: { nom: 'SARL Exemple' } }) },
    ))
    const apercu = await screen.findByTestId('apercu-modele')
    expect(within(apercu).getByText('Votre devis DEV-2026-0042')).toBeInTheDocument()
    expect(within(apercu).getByText('Bonjour SARL Exemple,')).toBeInTheDocument()
  })

  it('enregistre une modification du corps du modèle sélectionné', async () => {
    const user = userEvent.setup()
    get.mockResolvedValue({ data: MODELES })
    patch.mockResolvedValue({ data: {} })
    renderAvecRole('responsable')

    const ligne = await screen.findByTestId('modele-brande-email-relance_devis')
    await user.click(within(ligne).getByRole('button', { name: 'Relance de devis' }))

    const corps = await screen.findByDisplayValue('Bonjour {{ client.nom }},')
    await user.type(corps, ' merci.')
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))

    await waitFor(() => expect(patch).toHaveBeenCalledWith(
      '/core/branded-templates/7/',
      expect.objectContaining({ corps: 'Bonjour {{ client.nom }}, merci.' }),
    ))
  })

  it("un rôle simple lit les modèles mais n'a aucune commande d'écriture", async () => {
    get.mockResolvedValue({ data: MODELES })
    renderAvecRole('normal')

    await screen.findByTestId('modele-brande-email-relance_devis')
    expect(screen.queryByRole('button', { name: /Créer le modèle/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Supprimer le modèle/ })).toBeNull()
  })

  it('affiche une erreur de chargement sans planter', async () => {
    get.mockRejectedValue(new Error('boom'))
    renderAvecRole('admin')
    expect(await screen.findByText(/Impossible de charger les modèles brandés/))
      .toBeInTheDocument()
  })
})
