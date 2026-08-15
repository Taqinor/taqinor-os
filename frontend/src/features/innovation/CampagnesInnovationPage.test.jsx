import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// jsdom n'implémente pas ResizeObserver (DataTable/Radix Popover MultiSelect).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* WIR150 — `CampagneInnovationViewSet` (CRUD + incitation/rapport/cloner/
   tableau-bord/segments/historique/noter) n'avait aucun consommateur réel :
   seul `.incitation()` était appelé. Cet écran câble créer/lister/rapport/
   cloner. */

const {
  list, segmentsDisponibles, create, rapport, cloner,
  update, tableauBord, historique, noter,
} = vi.hoisted(() => ({
  // WIR213 — lancement/fermeture (PATCH statut), édition d'un brouillon,
  // tuiles du tableau de bord et chatter de campagne.
  update: vi.fn(() => Promise.resolve({ data: {} })),
  tableauBord: vi.fn(() => Promise.resolve({
    data: { actives: 1, brouillons: 2, fermees: 0, top_campagnes: [], taux_realisation: 0.25 },
  })),
  historique: vi.fn(() => Promise.resolve({ data: [] })),
  noter: vi.fn(() => Promise.resolve({
    data: [{
      id: 1, kind: 'note', body: 'Relancer les techniciens',
      user_username: 'reda', created_at: '2026-08-14T10:00:00Z',
    }],
  })),
  list: vi.fn(() => Promise.resolve({
    data: [{ id: 1, nom: 'Idées pompage', statut: 'active', statut_display: 'Active', segment: ['technicien'], date_debut: '2026-07-01', date_fin: null }],
  })),
  segmentsDisponibles: vi.fn(() => Promise.resolve({ data: { results: ['technicien', 'commercial'] } })),
  create: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
  rapport: vi.fn(() => Promise.resolve({
    data: { nb_utilisateurs_cibles: 5, nb_idees_proposees: 3, top_idees: [{ id: 9, titre: 'Idée A', votes_count: 4 }], taux_conversion: 0.4 },
  })),
  cloner: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
}))

vi.mock('../../api/innovationApi', () => ({
  default: {
    campagnes: {
      list, segmentsDisponibles, create, rapport, cloner,
      update, tableauBord, historique, noter,
    },
  },
}))

import CampagnesInnovationPage from './CampagnesInnovationPage'

beforeEach(() => { vi.clearAllMocks() })

describe('CampagnesInnovationPage (WIR150)', () => {
  it('liste les campagnes existantes', async () => {
    renderPage(<CampagnesInnovationPage />)
    // DataTable rend à la fois la table desktop et le repli carte mobile (CSS
    // seul, les deux existent dans le DOM en jsdom) : on cible le PREMIER
    // match, même patron que ModelesBcf.test.jsx / qhse.render.test.jsx.
    expect((await screen.findAllByText('Idées pompage'))[0]).toBeInTheDocument()
  })

  it('crée une campagne depuis le formulaire', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getByRole('button', { name: /Nouvelle campagne/ }))
    await user.type(screen.getByLabelText('Nom'), 'Relance O&M')
    await user.click(screen.getByRole('button', { name: 'Créer (brouillon)' }))

    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ nom: 'Relance O&M' })))
  })

  it('affiche le rapport d’une campagne', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getAllByRole('button', { name: 'Rapport' })[0])
    await waitFor(() => expect(rapport).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Idée A')).toBeInTheDocument()
  })

  it('clone une campagne', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getAllByRole('button', { name: 'Cloner' })[0])
    await waitFor(() => expect(cloner).toHaveBeenCalledWith(1))
  })
})

/* WIR213 — une campagne était structurellement inerte : jamais activable
   (brouillon à vie), ni éditable, ni dotée d'un tableau de bord ou d'un
   chatter. Quatre appels serveur existaient sans consommateur. */
describe('CampagnesInnovationPage — WIR213', () => {
  const BROUILLON = {
    id: 4, nom: 'Idées agricoles', statut: 'brouillon',
    statut_display: 'Brouillon', segment: ['technicien'],
    date_debut: null, date_fin: null, description: 'Pompage',
    message_incitation: '', tag_auto: '',
  }

  const ACTIVE = {
    id: 1, nom: 'Idées pompage', statut: 'active', statut_display: 'Active',
    segment: ['technicien'], date_debut: '2026-07-01', date_fin: null,
  }

  // `vi.clearAllMocks()` efface les APPELS, pas les implémentations : sans ce
  // re-armage, un `mockResolvedValue` posé dans un test fuirait dans le suivant.
  beforeEach(() => { list.mockResolvedValue({ data: [ACTIVE] }) })

  it('rend les tuiles du tableau de bord serveur', async () => {
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')
    expect(tableauBord).toHaveBeenCalled()
    expect(screen.getByText('Actives')).toBeInTheDocument()
    expect(screen.getByText('Brouillons')).toBeInTheDocument()
    // Taux SERVEUR (0.25) rendu tel quel en pourcentage — jamais recalculé.
    expect(screen.getByText('25%')).toBeInTheDocument()
  })

  it('crée puis lance une campagne (brouillon → active)', async () => {
    list.mockResolvedValue({ data: [BROUILLON] })
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées agricoles')

    // Un brouillon expose Modifier + Lancer, jamais Fermer.
    expect(screen.queryByRole('button', { name: 'Fermer' })).toBeNull()
    await user.click(screen.getAllByRole('button', { name: 'Lancer' })[0])
    await waitFor(() => expect(update).toHaveBeenCalledWith(4, { statut: 'active' }))
  })

  it('ferme une campagne active (active → fermée)', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    // Une campagne active expose Fermer, jamais Lancer ni Modifier.
    expect(screen.queryByRole('button', { name: 'Lancer' })).toBeNull()
    await user.click(screen.getAllByRole('button', { name: 'Fermer' })[0])
    await waitFor(() => expect(update).toHaveBeenCalledWith(1, { statut: 'fermee' }))
  })

  it('édite un brouillon sans jamais envoyer le statut', async () => {
    list.mockResolvedValue({ data: [BROUILLON] })
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées agricoles')

    await user.click(screen.getAllByRole('button', { name: 'Modifier' })[0])
    const champ = await screen.findByLabelText('Nom')
    await user.clear(champ)
    await user.type(champ, 'Idées agricoles v2')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(update).toHaveBeenCalledWith(
      4, expect.objectContaining({ nom: 'Idées agricoles v2' })))
    expect(update.mock.calls[0][1]).not.toHaveProperty('statut')
  })

  it('publie une note et relit la timeline du serveur', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getAllByRole('button', { name: 'Activité' })[0])
    await waitFor(() => expect(historique).toHaveBeenCalledWith(1))

    await user.type(await screen.findByLabelText('Ajouter une note'), 'Relancer les techniciens')
    await user.click(screen.getByRole('button', { name: 'Publier la note' }))

    await waitFor(() => expect(noter).toHaveBeenCalledWith(1, 'Relancer les techniciens'))
    // La timeline affichée vient de la RÉPONSE serveur (aucun ajout optimiste).
    expect(await screen.findByText(/Relancer les techniciens/)).toBeInTheDocument()
  })
})
