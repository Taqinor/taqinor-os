import { describe, it, expect, vi, beforeEach, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* VIS1 (fondateur 14/09/2026) — écran « Visiteurs & alertes ». Même patron que
   `RelancesSuiviPage.test.jsx` : le hook de rôle est mocké (réassignable par
   test) plutôt que de monter un vrai Provider redux. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const isAdminOrResponsableMock = vi.fn(() => false)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))

const {
  getAppareilsVisites, getVisitesExternes, getAppareilsEquipe,
  createAppareilEquipe, deleteAppareilEquipe, getLead,
} = vi.hoisted(() => ({
  getAppareilsVisites: vi.fn(),
  getVisitesExternes: vi.fn(),
  getAppareilsEquipe: vi.fn(),
  createAppareilEquipe: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
  deleteAppareilEquipe: vi.fn(() => Promise.resolve({ data: {} })),
  getLead: vi.fn(),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getAppareilsVisites: (...args) => getAppareilsVisites(...args),
    getVisitesExternes: (...args) => getVisitesExternes(...args),
    getAppareilsEquipe: (...args) => getAppareilsEquipe(...args),
    createAppareilEquipe: (...args) => createAppareilEquipe(...args),
    deleteAppareilEquipe: (...args) => deleteAppareilEquipe(...args),
    getLead: (...args) => getLead(...args),
  },
}))

import VisiteursPage from './VisiteursPage'

const APPAREIL_SUSPECT = {
  appareil_id: 'ab12cd34ef56', visites: 6, duree_totale_s: 725,
  premiere: '2026-09-01T10:00:00Z', derniere: '2026-09-10T14:00:00Z',
  propositions: 2, equipe: false,
  leads: [{ id: 1, nom: 'Ahmed Alami' }, { id: 2, nom: 'Sara B.' }],
}
const APPAREIL_EQUIPE = {
  appareil_id: 'ffff0000aaaa', visites: 30, duree_totale_s: 3600,
  premiere: '2026-08-01T10:00:00Z', derniere: '2026-09-12T14:00:00Z',
  propositions: 10, equipe: true,
  leads: [{ id: 3, nom: 'Karim T.' }],
}

// VIS-LEAD — mode `?lead=<id>` : forme RÉELLE de `GET /crm/leads/<id>/`
// (`nom`, `prenom`, `devis[]`) et de `devis[].lecture` (forme exacte de
// `apps.ventes.selectors.share_link_lecture_map` — jamais un champ inventé).
const LEAD_DEVIS = [
  {
    id: 41, reference: 'DV-2026-041', statut: 'envoye', total_ttc: '125000.00',
    date_creation: '2026-09-01T09:00:00Z', option_acceptee: null, chantier: null,
    share_link: null,
    lecture: {
      nombre_vues: 3,
      premiere_consultation: '2026-09-02T10:00:00Z',
      derniere_consultation: '2026-09-10T14:00:00Z',
    },
  },
  {
    id: 42, reference: 'DV-2026-042', statut: 'brouillon', total_ttc: '50000.00',
    date_creation: '2026-08-20T09:00:00Z', option_acceptee: null, chantier: null,
    share_link: null, lecture: null,
  },
]
const LEAD_DETAIL = { id: 7, nom: 'Alami', prenom: 'Ahmed', devis: LEAD_DEVIS }
const VISITE_LEAD_1 = {
  id: 501, point: 'proposition', point_display: 'Proposition', contexte: 'devis #41',
  ip: '41.1.2.3',
  user_agent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
  appareil_id: 'ffff0000aaaa', duree_s: 125, terminee: true, lead: 7, lead_nom: 'Ahmed Alami',
  created_at: '2026-09-10T14:00:00Z',
}

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(false)
  getAppareilsVisites.mockResolvedValue({ data: { results: [APPAREIL_SUSPECT, APPAREIL_EQUIPE] } })
  getAppareilsEquipe.mockResolvedValue({
    data: { results: [{ id: 5, appareil_id: 'ffff0000aaaa', libelle: 'Téléphone Reda', created_at: '2026-08-01T00:00:00Z' }] },
  })
  getVisitesExternes.mockResolvedValue({
    data: {
      results: [
        {
          id: 100, point: 'proposition', point_display: 'Proposition', contexte: 'devis #12',
          lead: 1, lead_nom: 'Ahmed Alami', duree_s: 90, ip: '41.1.2.3', created_at: '2026-09-10T14:00:00Z',
        },
      ],
    },
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount(initialEntries = ['/crm/visiteurs']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <VisiteursPage />
    </MemoryRouter>,
  )
}

describe('VisiteursPage (VIS1)', () => {
  it('liste les appareils avec leurs leads touchés et signale le cas multi-prospects', async () => {
    mount()
    await waitFor(() => expect(getAppareilsVisites).toHaveBeenCalled())

    expect(await screen.findByText('Ahmed Alami')).toBeInTheDocument()
    expect(screen.getByText('Sara B.')).toBeInTheDocument()
    expect(screen.getByText('Multi-prospects')).toBeInTheDocument()
    // L'appareil équipe ne porte jamais le badge suspect, même à 2+ leads.
    expect(screen.getAllByText('Équipe')).toHaveLength(1)
  })

  it('masque les actions d’exclusion équipe au rôle normal', async () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    mount()
    await waitFor(() => expect(getAppareilsVisites).toHaveBeenCalled())
    await screen.findByText('Ahmed Alami')

    expect(screen.queryByRole('button', { name: 'Marquer appareil équipe' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retirer de l’équipe' })).not.toBeInTheDocument()
    // Section « Appareils équipe » réservée elle aussi.
    expect(screen.queryByText('Appareils équipe')).not.toBeInTheDocument()
  })

  it('marque un appareil équipe (responsable/admin) avec un libellé optionnel', async () => {
    isAdminOrResponsableMock.mockReturnValue(true)
    const user = userEvent.setup()
    mount()
    await screen.findByText('Ahmed Alami')

    await user.click(screen.getByRole('button', { name: 'Marquer appareil équipe' }))
    await user.type(screen.getByLabelText('Libellé (optionnel)'), 'Téléphone Reda')
    await user.click(screen.getByRole('button', { name: 'Marquer équipe' }))

    await waitFor(() => expect(createAppareilEquipe).toHaveBeenCalledWith({
      appareil_id: 'ab12cd34ef56', libelle: 'Téléphone Reda',
    }))
    // Refresh des deux listes après la mutation.
    await waitFor(() => expect(getAppareilsVisites).toHaveBeenCalledTimes(2))
    expect(getAppareilsEquipe).toHaveBeenCalledTimes(2)
  })

  it('retire un appareil de l’équipe via la ligne de la section dédiée', async () => {
    isAdminOrResponsableMock.mockReturnValue(true)
    const user = userEvent.setup()
    mount()
    await screen.findByText('Appareils équipe')
    expect(screen.getByText('Téléphone Reda')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Retirer' })[0])
    await waitFor(() => expect(deleteAppareilEquipe).toHaveBeenCalledWith(5))
  })

  it('déplie le détail des visites récentes d’un appareil', async () => {
    const user = userEvent.setup()
    mount()
    await screen.findByText('Ahmed Alami')

    await user.click(screen.getByText('ab12cd34…'))
    await waitFor(() => expect(getVisitesExternes).toHaveBeenCalledWith({ appareil_id: 'ab12cd34ef56' }))
    expect(await screen.findByText('devis #12')).toBeInTheDocument()
  })

  it('pré-filtre sur l’appareil du lien profond (?appareil=)', async () => {
    mount(['/crm/visiteurs?appareil=ab12cd34ef56'])
    await waitFor(() => expect(getAppareilsVisites).toHaveBeenCalledWith({ appareil_id: 'ab12cd34ef56' }))
    expect(screen.getByText(/Filtré sur l’appareil/)).toBeInTheDocument()
  })
})

/* VIS-LEAD (14-16/09/2026) — la notification `devis_opened` pointe désormais
   `/crm/visiteurs?lead=<id>` : cet écran doit montrer l'historique des accès
   de CE lead (lectures des devis + visites brutes), pas la liste agrégée par
   appareil. */
describe('VisiteursPage — mode lead (?lead=), historique des accès (VIS-LEAD)', () => {
  beforeEach(() => {
    getLead.mockResolvedValue({ data: LEAD_DETAIL })
    getVisitesExternes.mockResolvedValue({ data: { results: [VISITE_LEAD_1] } })
  })

  it('charge la fiche et les visites du lead, et affiche son historique', async () => {
    mount(['/crm/visiteurs?lead=7'])

    await waitFor(() => expect(getLead).toHaveBeenCalledWith('7'))
    await waitFor(() => expect(getVisitesExternes).toHaveBeenCalledWith({ lead: '7' }))

    expect(await screen.findByText(/Historique des accès — Alami Ahmed/)).toBeInTheDocument()
    // Ligne d'accès : point_display, IP, durée humanisée (125 s -> 2 min).
    expect(screen.getByText(/Proposition/)).toBeInTheDocument()
    expect(screen.getByText('41.1.2.3')).toBeInTheDocument()
    expect(screen.getByText('2 min')).toBeInTheDocument()
    // L'appareil de cette visite est déjà marqué équipe (APPAREIL_EQUIPE) :
    // le badge doit apparaître sur sa ligne d'accès.
    expect(screen.getByText('Équipe')).toBeInTheDocument()
  })

  it('affiche « Jamais partagé » pour un devis sans lien, et le compteur réel pour un devis lu', async () => {
    mount(['/crm/visiteurs?lead=7'])
    await screen.findByText(/Historique des accès/)

    expect(screen.getByText(/Jamais partagé/)).toBeInTheDocument()
    expect(screen.getByText(/Ouvert 3 fois/)).toBeInTheDocument()
  })

  it('affiche le message vide quand le lead n’a aucun accès enregistré', async () => {
    getVisitesExternes.mockResolvedValue({ data: { results: [] } })
    mount(['/crm/visiteurs?lead=7'])
    await screen.findByText(/Historique des accès/)

    expect(await screen.findByText('Aucun accès enregistré pour ce lead.')).toBeInTheDocument()
  })

  it('« Tous les appareils » retire le filtre lead et revient à la vue agrégée', async () => {
    const user = userEvent.setup()
    mount(['/crm/visiteurs?lead=7'])
    await screen.findByText(/Historique des accès/)

    await user.click(screen.getByRole('button', { name: 'Tous les appareils' }))

    await waitFor(() => expect(getAppareilsVisites).toHaveBeenCalled())
    expect(screen.queryByText(/Historique des accès/)).not.toBeInTheDocument()
  })
})
